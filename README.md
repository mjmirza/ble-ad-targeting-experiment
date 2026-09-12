# BLE Ad Targeting Experiment

![status](https://img.shields.io/badge/status-archived%20experiment-orange)
![license](https://img.shields.io/badge/license-ORA%20(own%20risk)-red)
![python](https://img.shields.io/badge/python-3.10%2B-green)
![stack](https://img.shields.io/badge/stack-bleak%20%2B%20vanilla%20JS-lightgrey)

Status. Archived experiment. Kept as a documented journey, not under active development.

> Use at your own risk. This is published under the ORA License (Own Risk Attribution), not MIT and not open source. It observes radio signals, and capturing or processing device or personal data is regulated in many places. Everyone is responsible for their own use, their own risk, and their own legal compliance. The author accepts no responsibility or liability for anything anyone does with it. See LICENSE.

> The experiment. We wanted to know if a passive Bluetooth box at a venue door could capture the phones walking past and turn them into a Facebook, Google, Amazon, or TikTok ad audience. We built a live capture rig and a full analysis dashboard, measured it on real hardware, and found that it cannot. So we chose not to pursue it. This repository documents the whole journey, the working code, and the honest finding, so the next person does not spend a week rediscovering the same wall.

## What this is

A live Bluetooth Low Energy scanner plus a single self-contained web dashboard. It listens to every device broadcasting nearby and shows, in real time, who is in range, how long they stay, how close they are, what type of device they carry, and every arrival and departure. It deduplicates rotating identifiers and lays out the honest pipeline into the major ad platforms.

## The finding (why we stopped)

- A passive scan captures presence, not identity. Across 214 unique devices in one session, the count carrying a usable advertising identifier was zero.
- Phones broadcast a rotating, random Bluetooth address, never the Apple IDFA or the Google advertising ID. Ad platforms match on IDFA, GAID, or a hashed email or phone, so a Bluetooth address is not something any of them can ingest.
- Consent does not change this. The advertising identifier is simply not in the radio packet. It lives only inside software running on the phone.
- The data is genuinely useful for footfall and movement research. It is not useful for ad targeting.

## What actually reaches an ad platform (the honest alternatives)

- Platform location targeting. Meta, Google, Amazon, and TikTok can all target a radius around a venue with no capture at all.
- Addressable geofencing through a demand-side platform. A vendor builds a "was physically here" audience from consented app-SDK location data.
- A Wi-Fi captive portal or opt-in. The venue itself collects an email or phone, hashes it, and uploads it as a custom audience.

None of these use the Bluetooth box. That is the point of the experiment.

## What you get

- A real-time presence dashboard. In range now, recently left, total ever, all deduplicated.
- A live scanner that logs every arrival and departure to disk.
- An interactive walk-through and a per-platform funnel for Amazon, Meta, Google, and TikTok.
- A BLE signal menu showing what each signal reveals, and a clear list of what is never in the packet.

## Technical overview

- Scanner. Python with the bleak library. One continuous BLE scan, with presence and deduplication logic.
- Dashboard. A single self-contained HTML file. Vanilla JavaScript, no build step, no runtime dependencies.
- Live feed. The scanner writes a small JSON snapshot every two seconds. The page polls it and animates arrivals and departures.
- Storage. Every arrival and departure is appended to a JSONL log on disk, so nothing is lost.
- Deduplication. Rotating Bluetooth addresses and flapping in and out of range are collapsed into one logical device by a stable fingerprint, with anonymous phones honestly marked as un-linkable.

## Getting started

Prerequisites. Python 3.10 or newer, and a machine with Bluetooth.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# live feed. serve the page and the scanner from one folder
mkdir -p public && cp index.html public/
.venv/bin/python scripts/live_scan.py ./public &
.venv/bin/python -m http.server 8777 --directory ./public
```

Then open http://localhost:8777 in a browser.

For a one-shot capture instead of the live feed, run `.venv/bin/python scripts/capture.py 25` to write `ble_data.json`, then `.venv/bin/python scripts/build_page.py` to regenerate the dashboard.

## Project structure

```
index.html             the self-contained dashboard (embeds a captured snapshot)
requirements.txt       python dependency (bleak)
data/ble_data.json     the captured snapshot that powers the static page
scripts/capture.py     one-shot BLE scan to JSON
scripts/live_scan.py   continuous live scanner with presence and dedupe
scripts/build_page.py  generates index.html from the snapshot
AGENTS.md              guidance for AI agents reading this repo
LICENSE                ORA (own risk) license
```

## A note on privacy

Every identifier in the captured data is an ephemeral, per-scan random value that modern phones rotate for privacy. Device names shown are the public Bluetooth broadcast names of nearby hardware. No advertising identifier, phone number, email, or account is present, because none of that is ever broadcast over Bluetooth. That is precisely the finding this repository documents.

## License

ORA License (Own Risk Attribution). Not MIT, not open source. Use entirely at your own risk. No warranty, no liability, and you indemnify the author. Legal compliance in your own jurisdiction is your responsibility alone. Credit required. Commercial use by written permission. See LICENSE for the full terms and AGENTS.md for the machine-readable summary.

## Trademarks

Amazon and Amazon DSP are trademarks of Amazon.com, Inc. or its affiliates. Meta, Instagram, Facebook, Google, YouTube, and TikTok are trademarks of their respective owners. This repository is an independent experiment and is not affiliated with, endorsed by, or sponsored by any of them.
