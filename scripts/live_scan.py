import asyncio, json, os, sys, time, collections
from bleak import BleakScanner

OUTDIR = (
    sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
)
os.makedirs(OUTDIR, exist_ok=True)
LIVE = os.path.join(OUTDIR, "ble_live.json")
LIVE_TMP = LIVE + ".tmp"
EVENTS = os.path.join(
    OUTDIR, "ble_events.jsonl"
)  # deduped log of logical devices coming & going

PRESENCE_TIMEOUT = 18  # no packet for this long => drop from the "in range now" grid
REJOIN_GRACE = 90  # returns within this = same visit (flap), NOT a new arrival
GONE_AFTER = 90  # no packet for this long => a confirmed departure

COMPANY = {
    76: "Apple",
    117: "Samsung",
    6: "Microsoft",
    224: "Google",
    89: "Nordic Semi",
    15: "Broadcom",
    301: "Bose",
    1447: "Logitech",
    1744: "Anker/Soundcore",
    93: "Realtek",
}
GENERIC_MFR = (
    [76],
    [117],
    [6],
    [224],
)  # bare phone-vendor id, no distinguishing signal


def norm_rssi(r):
    return r if (r is not None and -110 <= r <= -20) else -99


def categorize(name, mids):
    n = (name or "").lower()

    def has(*ks):
        return any(k in n for k in ks)

    if n:
        if has("lime", "bike", "scoot", "voi", "tier"):
            return "Vehicle / scooter"
        if has("watch", "band", " fit", "fit ", "galaxy watch", "ring", "tracker"):
            return "Wearable"
        if has(
            "bud",
            "airpod",
            "aero",
            "soundcore",
            "core400",
            "bose",
            "marshall",
            "stanmore",
            "headphone",
            "speaker",
            "jbl",
            "beats",
            "sony w",
        ):
            return "Audio"
        if has(
            "tv",
            "bravia",
            "firetv",
            "fire tv",
            "chromecast",
            "roku",
            "apple tv",
            "webos",
            "googlecast",
            "shield",
            "[tv]",
        ):
            return "TV / media"
        if has("hue", "light", "strip", "lamp", "plug", "nest", "echo", "dot", "bulb"):
            return "Smart home"
        if has("macbook", "imac", "laptop", "surface", "thinkpad", " pc"):
            return "Computer"
        if has(
            "iphone",
            "pixel",
            "galaxy s",
            "galaxy a",
            "redmi",
            "oneplus",
            "xiaomi",
            "phone",
        ):
            return "Phone (named)"
        return "Other named device"
    if 76 in mids:
        return "Apple (anonymised)"
    if 117 in mids:
        return "Samsung (anonymised)"
    return "Anonymous device"


def fingerprint(addr, name, mids, svcs):
    # Returns (key, can_dedupe). A distinctive signal lets us collapse rotated addresses
    # into one logical device. A bare randomised phone cannot be de-duped by design.
    if name:
        return "n:" + name.strip().lower(), True
    if svcs:
        return "s:" + ",".join(sorted(svcs)) + "|m:" + ",".join(map(str, mids)), True
    if mids and mids not in GENERIC_MFR:
        return "m:" + ",".join(map(str, mids)), True
    return "a:" + addr, False


logical = {}  # fp -> record (one real device)
packet_times = collections.deque(maxlen=6000)
events = collections.deque(maxlen=30)
t0 = time.time()
arrivals = 0  # confirmed logical arrivals (first sight + genuine returns)
departures = 0  # confirmed logical departures


def log_event(kind, rec):
    ev = {
        "ts": round(time.time(), 2),
        "clock": time.strftime("%H:%M:%S"),
        "kind": kind,
        "fp": rec["fp"],
        "name": rec.get("name") or "(anonymous)",
        "cat": rec["cat"],
        "rssi": rec.get("rssi"),
        "ids": len(rec["addrs"]),
    }
    events.appendleft(ev)
    try:
        with open(EVENTS, "a") as f:
            f.write(json.dumps(ev) + "\n")
    except OSError as e:
        print("event log write failed:", e, file=sys.stderr, flush=True)


def cb(device, adv):
    global arrivals
    now = time.time()
    addr = device.address
    mids = sorted(adv.manufacturer_data.keys())
    svcs = list(adv.service_uuids or [])
    name = adv.local_name or device.name
    fp, can = fingerprint(addr, name, mids, svcs)

    rec = logical.get(fp)
    if rec is None:
        arrivals += 1
        rec = {
            "fp": fp,
            "first": now,
            "name": name,
            "addrs": {addr},
            "can_dedupe": can,
            "cat": categorize(name, mids),
            "maker": (COMPANY.get(mids[0], f"Company #{mids[0]}") if mids else "—"),
            "rssi": norm_rssi(adv.rssi),
            "last": now,
            "departed": False,
        }
        logical[fp] = rec
        log_event("in", rec)
    else:
        if rec["departed"] and (now - rec["last"] > GONE_AFTER):
            arrivals += 1  # genuine return after a real absence
            rec["departed"] = False
            log_event("in", rec)
        else:
            rec["departed"] = False  # flap / rotation within grace = same visit, silent
        rec["name"] = rec.get("name") or name
        rec["cat"] = categorize(rec.get("name"), mids)
        if rec["maker"] in (None, "—") and mids:
            rec["maker"] = COMPANY.get(mids[0], f"Company #{mids[0]}")
    rec["addrs"].add(addr)
    rec["rssi"] = norm_rssi(adv.rssi)
    rec["last"] = now
    packet_times.append(now)


def expire():
    global departures
    now = time.time()
    for rec in logical.values():
        if not rec["departed"] and now - rec["last"] > GONE_AFTER:
            rec["departed"] = True
            departures += 1
            log_event("out", rec)


def snapshot():
    now = time.time()
    win = [t for t in packet_times if now - t <= 5]
    present = [r for r in logical.values() if now - r["last"] <= PRESENCE_TIMEOUT]
    present.sort(key=lambda r: -r["rssi"])
    cats = collections.Counter(r["cat"] for r in present)
    unique_ever = len(logical)
    merged = sum(
        len(r["addrs"]) - 1 for r in logical.values()
    )  # extra addresses collapsed away
    dep = sorted(
        (r for r in logical.values() if r["departed"]), key=lambda r: -r["last"]
    )
    return {
        "live": True,
        "started_at": time.strftime("%H:%M:%S", time.localtime(t0)),
        "elapsed": round(now - t0),
        "updated": time.strftime("%H:%M:%S", time.localtime(now)),
        "present_count": len(present),
        "unique_ever": unique_ever,  # deduped logical devices
        "raw_addresses": unique_ever
        + merged,  # sightings before dedupe (consistent, >= unique)
        "dedup_removed": merged,  # duplicate addresses collapsed into their real device
        "arrivals": arrivals,
        "departures": departures,
        "pps": round(len(win) / 5.0, 1),
        "apple": sum(1 for r in present if r["cat"].startswith("Apple")),
        "targetable_ad_ids": 0,
        "cats": dict(cats.most_common()),
        "present": [
            {
                "fp": r["fp"],
                "name": r.get("name") or "(anonymous)",
                "cat": r["cat"],
                "maker": r.get("maker", "—"),
                "rssi": r["rssi"],
                "ids": len(r["addrs"]),
                "can_dedupe": r["can_dedupe"],
                "dwell": round(now - r["first"]),
            }
            for r in present[:48]
        ],
        "departed_count": unique_ever - len(present),
        "departed": [
            {
                "fp": r["fp"],
                "name": r.get("name") or "(anonymous)",
                "cat": r["cat"],
                "maker": r.get("maker", "—"),
                "rssi": r["rssi"],
                "ids": len(r["addrs"]),
                "dwell": round(r["last"] - r["first"]),
                "gone": round(now - r["last"]),
            }
            for r in dep[:40]
        ],
        "events": list(events),
    }


def write():
    expire()
    with open(LIVE_TMP, "w") as f:
        json.dump(snapshot(), f, separators=(",", ":"))
    os.replace(LIVE_TMP, LIVE)


async def run():
    write()
    scanner = BleakScanner(cb)
    await scanner.start()
    try:
        while True:
            await asyncio.sleep(2)
            write()
    finally:
        await scanner.stop()


async def main():
    while True:
        try:
            await run()
        except Exception as e:
            print("scanner restart after error:", e, file=sys.stderr, flush=True)
            await asyncio.sleep(3)


asyncio.run(main())
