+++
title = "Verified results & limits"
description = "What was tested on the camera, what the host tests cover, and what remains unverified."
weight = 20
+++

The public result summary contains only selected non-identifying observations. Raw API responses, process snapshots, credentials, device/configuration dumps and full journals remain private. Their absence from the public repository limits independent reproduction of past device-specific observations; the included tools can reproduce the documented read-only analyses on supplied inputs.

## Observed progression

| Date, UTC | Milestone | Evidence boundary |
|---|---|---|
| 2026-11-16 | Stock 1.3.17 package acquired and analyzed; compatibility fields read locally | Original hardware/build, not all C200 revisions |
| 2026-11-16 | Normal authenticated HTTP downgrade to stock 1.1.15 | Post-boot identity/version/firmware-ID reads confirmed completion |
| 2026-11-16 | Existing root Telnet verified; nine partition readbacks independently checked | Backups, not a tested physical recovery procedure |
| 2026-11-16 | Temporary OUTPUT isolation and selective RAM watchdog experiment | Warm running-system checks only |
| 2026-11-17 | ART examined offline; bootstrap RAM trial passed | Modified ART was never written |
| 2026-11-17 | Saved firewall interpretation path demonstrated | First proof used scratch configuration and stubbed rules |
| 2026-11-17 | Initial configuration save restored files but failed to start Telnet | Shadow-only root-account assumption was wrong; owner recovered access |
| 2026-11-17 07:57 | Corrected Telnet startup survived reboot | Root/password login and filter passed; RTSP DESCRIBE stalled |
| 2026-11-17 09:06 | Exact Live555 multicast exception restored RTP immediately | Runtime change, no service restart required |
| 2026-11-17 09:28 | Final startup/configuration save and physical readback passed | Only user-config partition changed |
| 2026-11-17 09:32 | One requested normal reboot of the final fix | Telnet, API and RTP returned automatically |
| 2026-11-17 09:34 | Both video streams independently decoded | 75 frames per stream over five-second probe intervals |
| 2026-11-17 09:35 | Fresh root/API/RTP at 205.87 s uptime | Beyond first 180-second watchdog scan; bounded stability |
| 2026-11-17 09:44 | ONVIF capabilities/profiles/URIs and unicast discovery passed | Read-only requests, no physical movement |

## Final persistence acceptance

The final candidate was first exercised in a device-free chroot. A bounded file-I/O adapter redirected the stock configuration utility to ordinary files; the sandbox had no physical flash device nodes. Two complete candidate save/restore cycles matched expected files. Direct-hash, shadow-backed, empty and locked account fixtures checked normal authentication guards without altering live accounts.

Live staging then checked a fresh normal-password login, empty-password rejection, repeat launch with the same listener PID and local RTP. All physical flash/account hashes stayed unchanged during this stage. This distinction matters because an earlier realistic-looking fixture had missed the stock direct-hash account layout.

The explicit final save used the normal stock utility. Only `/dev/mtdblock3` changed. Its physical 65,536-byte readback restored the expected configuration files twice. Password files matched their pre-save checksums.

After one requested normal reboot, acceptance required:

- A lower uptime than before reboot, and fresh authenticated root/API/RTP sessions.
- Empty-password refusal and unchanged account files.
- Expected saved startup file checksums and an attached OUTPUT filter.
- Encryption ON and the exact Live555 rule present.
- All nine flash hashes matching the verified saved state.

The later bounded stability check repeated root/API/RTP, account/flash invariants, synchronization and encryption state after the first watchdog interval. All passed.

## Decoded video and ONVIF

| Stream | Codec | Dimensions | Decoded frames | Probe interval |
|---|---|---|---:|---|
| stream1 | H.264 | 1920×1080 | 75 | 5 seconds |
| stream2 | H.264 | 640×360 | 75 | 5 seconds |

FFprobe used TCP RTSP and bounded timeouts. Credentials were loaded through temporary private argument files, absent from process arguments/environment/logs, and the temporary files were deleted. Logging was disabled. Only codec, dimensions and frame counts were retained; no media was saved. These short probes do not measure hours of uninterrupted streaming.

ONVIF authenticated capabilities/profile/stream-URI requests returned 200 without SOAP faults. Both profiles pointed at the tested RTSP paths. UDP unicast discovery responded. PTZ, events, recording and audio behavior were not exercised.

## Failed hypotheses and corrections retained in the record

- Correcting the 2021 clock did not independently fix the RTSP stall.
- Temporary media-encryption OFF did not fix it; ON was restored before save and verified after boot. No code/keys were altered.
- Encoder/RTSP callbacks and a temporary cloud-process shutdown did not solve it. Stock processes now run behind the filter.
- A hardware/ISP reload attempt stopped at its duplicate-process guard. No successful full ISP reload is claimed.
- An uptime reset was observed during earlier media diagnostics without an assistant reboot request; its cause was not established. Persistent Telnet returned. This remains relevant to long-duration validation.
- Ordinary `uci commit` was incorrectly treated as RAM-only earlier. On this firmware it can invoke the saver; approved NTP commits changed user configuration. Earlier reports' intended-scope labels do not override physical checksum observations.
- A successful firmware upload response was not treated as proof of downgrade; subsequent identity/version reads supplied that evidence.

## Host tools

```sh
uv sync --locked --group analysis
uv run --locked python -m unittest discover -s tests -v
```

Publication preparation run on 2026-11-17: **54 tests passed**, including the localhost integration check, optional pinned-firmware cases, portable uploader checks and public bootstrap fixtures. All five reference assets matched their pinned size/SHA-256, all local Markdown links resolved, and all seven CLI help entry points passed.

The suite covers malformed image boundaries, hash mismatches, extraction overwrite refusal, path traversal/symlink handling, TCP classification, selected API reads, secret-free diagnostics and compatibility comparisons. The added tests exercise multipart byte preservation, one-send behavior on disconnect, retry rejection and explicit write-mode prerequisites. Bootstrap fixtures execute the real shell flow with temporary filesystem paths and stubbed firewall/network/listener commands, covering direct/shadow/empty/locked accounts, unchanged account files, repeated launches and media/discovery rules. The localhost integration test skips when binding is prohibited. No test requires contacting a camera.

Website checks also cover root/subpath hosting, missing assets, exact bootstrap downloads, and rejecting unlisted static inputs before a build. Hugo built and checked 13 HTML pages, including a GitHub Pages-style subpath. Desktop/mobile browser QA passed search, dark mode, navigation, downloads and overflow checks, with no page errors, failed requests or external browser requests.

The CI/privacy checks distinguish the documented stock default from custom credentials, reject forced tracked files outside the public list, and scan rendered output and public JSON for account/unit fields. The GitHub Actions workflow also passed `actionlint` syntax/expression validation. See the [privacy review](privacy.md) for the classification and limits.

The public uploader is adapted from the successful one-off uploader. The bootstrap differs from the final installed bytes only in its example LAN address. These public adaptations have offline/host tests, not a second live downgrade/install claim. See the [downgrade](../guide/downgrade.md) and [persistence](../guide/permanent-telnet.md) procedures for write boundaries.

Firmware-dependent cases skip when the optional exact 1.1.15 image is not at the collector's default location. To enable them after checksum-verified reference download:

```sh
uv run --locked python scripts/fetch_assets.py
mkdir -p firmware/v2-1.1.15
cp work/downloads/c200v2-1.1.15.bin firmware/v2-1.1.15/Tapo_C200v2_en_1.1.15_Build_211112_Rel.10589n__1637888842077.bin
uv run --locked python -m unittest discover -s tests -v
```

The candidate loader verifies exact length and SHA-256 before using the image. Firmware and generated reports remain ignored. The publication bundle is also checked in isolation, where no private device material or firmware is present.

## Still unverified

- Long uninterrupted streaming and repeated physical power cycles.
- Upstream traffic capture spanning boot, and IPv6 enforcement.
- DHCP address changes, Wi-Fi reassociation and full firewall reloads.
- Audio, events, recording, SD removal, PTZ and IR/day-night transitions under isolation.
- Physical board/flash/SoC identification, serial access and a tested recovery procedure.
- A supported custom-firmware build or acceptance of modified firmware.

The current milestones are authenticated shell persistence and functioning local media on one stock-firmware unit. They do not establish every aspect of unattended local-only deployment.
