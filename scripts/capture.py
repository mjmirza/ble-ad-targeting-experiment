import asyncio, sys, json, time
from bleak import BleakScanner

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
    65535: "Test/Internal",
}

devices = {}
samples = []
t0 = 0.0


def classify_name(name):
    if not name:
        return "anonymous"
    n = name.lower()
    if any(k in n for k in ("watch", "band", "fit", "ring")):
        return "wearable"
    if any(
        k in n
        for k in (
            "bud",
            "sound",
            "aero",
            "core",
            "stanmore",
            "bose",
            "airpod",
            "headphone",
        )
    ):
        return "audio"
    if "lime" in n or "bike" in n or "scoot" in n:
        return "vehicle"
    if any(k in n for k in ("hue", "light", "strip", "lamp", "tv", "cast")):
        return "smart-home"
    return "named-device"


def cb(device, adv):
    ts = time.time() - t0
    addr = device.address
    mfr_ids = sorted(adv.manufacturer_data.keys())
    if addr not in devices:
        devices[addr] = {
            "id": addr,
            "name": adv.local_name or device.name,
            "mfr_ids": mfr_ids,
            "mfr_names": [COMPANY.get(m, f"Company #{m}") for m in mfr_ids],
            "services": list(adv.service_uuids)[:3],
            "rssi_min": adv.rssi,
            "rssi_max": adv.rssi,
            "rssi_last": adv.rssi,
            "first_seen": round(ts, 2),
            "last_seen": round(ts, 2),
            "hits": 0,
        }
    d = devices[addr]
    if not d["name"] and (adv.local_name or device.name):
        d["name"] = adv.local_name or device.name
    d["rssi_last"] = adv.rssi
    d["rssi_min"] = min(d["rssi_min"], adv.rssi)
    d["rssi_max"] = max(d["rssi_max"], adv.rssi)
    d["last_seen"] = round(ts, 2)
    d["hits"] += 1
    samples.append([round(ts, 2), addr, adv.rssi])


async def main(secs):
    global t0
    t0 = time.time()
    scanner = BleakScanner(cb)
    await scanner.start()
    await asyncio.sleep(secs)
    await scanner.stop()

    for d in devices.values():
        d["category"] = classify_name(d["name"])

    def has_targetable_id(d):
        blob = json.dumps(d).lower()
        for token in ("@", "aaid", "idfa", "gaid", "email_hash"):
            if token in blob:
                return token
        return None

    targetable = [d["id"] for d in devices.values() if has_targetable_id(d)]

    out = {
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)),
        "scan_seconds": secs,
        "host": "MacBook (CoreBluetooth passive scan)",
        "total_devices": len(devices),
        "total_adv_packets": len(samples),
        "named": sum(1 for d in devices.values() if d["name"]),
        "anonymous": sum(1 for d in devices.values() if not d["name"]),
        "apple": sum(1 for d in devices.values() if 76 in d["mfr_ids"]),
        "targetable_ad_ids": len(targetable),
        "devices": sorted(devices.values(), key=lambda x: -x["rssi_max"]),
        "samples": samples,
    }
    with open("ble_data.json", "w") as f:
        json.dump(out, f, indent=1)
    print(
        f"devices={out['total_devices']} packets={out['total_adv_packets']} "
        f"named={out['named']} apple={out['apple']} targetable_ad_ids={out['targetable_ad_ids']}"
    )


asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 25))
