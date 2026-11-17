+++
title = "Verified results & limits"
description = "What was tested on the camera, what the host tests cover, and what remains unverified."
weight = 20
+++

The result summary includes selected observations that do not identify the camera or account. Raw API responses, process snapshots, credentials, device and configuration dumps, and full logs stay private. Without those files, readers cannot independently check every observation from the original camera. The included tools can repeat the documented read-only analyses on files you supply.

## Observed progression

| Date, UTC | Result | What was checked |
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
| 2026-11-17 09:32 | One normal reboot with the final fix | Telnet, API and RTP returned automatically |
| 2026-11-17 09:34 | Both video streams independently decoded | 75 frames per stream over five-second probe intervals |
| 2026-11-17 09:35 | Fresh root/API/RTP at 205.87 s uptime | Beyond first 180-second watchdog scan; short stability check |
| 2026-11-17 09:44 | ONVIF capabilities/profiles/URIs and unicast discovery passed | Read-only requests, no physical movement |

## Checks after saving and rebooting

The proposed configuration was first tested in an isolated chroot. An adapter redirected the stock configuration utility to ordinary files, with no access to physical flash devices. Two complete save/restore cycles produced the expected files. Separate direct-hash, shadow-backed, empty and locked account fixtures tested the login guards without changing accounts on the camera.

The RAM trial on the camera checked a fresh password login, empty-password rejection, a repeat launch with the same listener PID, and local RTP. Flash and account checksums stayed unchanged. An earlier test fixture had missed the stock direct-hash account layout, so the live account checks were also needed.

The final configuration was saved with the stock utility. Only `/dev/mtdblock3` changed. Its physical 65,536-byte readback restored the expected configuration files twice. Password files matched their pre-save checksums.

After one normal reboot, the camera passed these checks:

- A lower uptime than before reboot, and fresh authenticated root/API/RTP sessions.
- Empty-password refusal and unchanged account files.
- Expected saved startup file checksums and an attached OUTPUT filter.
- Encryption ON and the exact Live555 rule present.
- All nine flash hashes matching the verified saved state.

After the first watchdog interval, fresh root/API/RTP sessions still worked. Account and flash checksums, time synchronization and encryption state also passed again. This was a short stability check.

## Decoded video and ONVIF

| Stream | Codec | Dimensions | Decoded frames | Probe interval |
|---|---|---|---:|---|
| stream1 | H.264 | 1920×1080 | 75 | 5 seconds |
| stream2 | H.264 | 640×360 | 75 | 5 seconds |

FFprobe used TCP RTSP and bounded timeouts. Credentials were loaded through temporary private argument files, absent from process arguments/environment/logs, and the temporary files were deleted. Logging was disabled. Only codec, dimensions and frame counts were retained; no media was saved. These short probes do not measure hours of uninterrupted streaming.

ONVIF authenticated capabilities/profile/stream-URI requests returned 200 without SOAP faults. Both profiles pointed at the tested RTSP paths. UDP unicast discovery responded. PTZ, events, recording and audio behavior were not exercised.

## What did not work

- Correcting the 2021 clock did not independently fix the RTSP stall.
- Temporary media-encryption OFF did not fix it; ON was restored before save and verified after boot. No code/keys were altered.
- Encoder/RTSP callbacks and a temporary cloud-process shutdown did not solve it. Stock processes now run behind the filter.
- A hardware/ISP reload attempt stopped at its duplicate-process guard, so a full ISP reload was not completed.
- The uptime reset unexpectedly during earlier media diagnostics. No reboot had been requested as part of those diagnostics, and the cause is unknown. Persistent Telnet returned afterward, but long-running stability still needs testing.
- Ordinary `uci commit` was initially mistaken for a RAM-only operation. On this firmware it can invoke the flash saver: commits of NTP settings changed the user-configuration partition. Physical checksums confirmed the writes.
- A successful firmware upload response was not treated as proof of downgrade; subsequent identity/version reads supplied that evidence.

## Host tools

```sh
uv sync --locked --group analysis
uv run --locked python -m unittest discover -s tests -v
```

On 2026-11-17, **54 tests passed**, including the localhost integration check, optional pinned-firmware cases, uploader checks and startup-script fixtures. All five reference assets matched their pinned size/SHA-256, all local Markdown links resolved, and all seven CLI help entry points passed.

The suite covers malformed image boundaries, hash mismatches, extraction overwrite refusal, path traversal/symlink handling, TCP classification, selected API reads, secret-free diagnostics and compatibility comparisons. Uploader tests check that multipart encoding preserves every image byte, a disconnect causes no resend, retries are rejected, and write mode requires its specified inputs. Bootstrap fixtures execute the real shell flow with temporary filesystem paths and stubbed firewall/network/listener commands, covering direct/shadow/empty/locked accounts, unchanged account files, repeated launches and media/discovery rules. The localhost integration test skips when binding is prohibited. No test requires contacting a camera.

Website checks also cover root/subpath hosting, missing assets, exact bootstrap downloads, and rejecting unlisted static inputs before a build. Hugo built and checked 15 HTML pages, including a GitHub Pages-style subpath. Desktop and mobile browser checks passed search, dark mode, navigation, downloads and page-width checks. There were no page errors, failed requests or external browser requests.

The CI/privacy checks distinguish the documented stock default from custom credentials, reject forced tracked files outside the public list, and scan rendered output and public JSON for account/unit fields. The GitHub Actions workflow also passed `actionlint` syntax/expression validation. See the [privacy review](privacy.md) for the classification and limits.

The repository's uploader is adapted from the client used for the successful downgrade. The startup scripts differ from the installed files only in their example LAN address. Both have been tested on a computer, but have not been used for a second camera downgrade or installation. The [downgrade](../guide/downgrade.md) and [permanent Telnet](../guide/permanent-telnet.md) guides mark the steps that write flash.

Firmware-dependent cases skip when the optional exact 1.1.15 image is not at the collector's default location. To enable them after checksum-verified reference download:

```sh
uv run --locked python scripts/fetch_assets.py
mkdir -p firmware/v2-1.1.15
cp work/downloads/c200v2-1.1.15.bin firmware/v2-1.1.15/Tapo_C200v2_en_1.1.15_Build_211112_Rel.10589n__1637888842077.bin
uv run --locked python -m unittest discover -s tests -v
```

The candidate loader verifies exact length and SHA-256 before using the image. Firmware and generated reports remain ignored. The source export is also checked in a separate directory without private device files or firmware.

## Still unverified

- Long uninterrupted streaming and repeated physical power cycles.
- Upstream traffic capture spanning boot, and IPv6 enforcement.
- DHCP address changes, Wi-Fi reassociation and full firewall reloads.
- Audio, events, recording, SD removal, PTZ and IR/day-night transitions under isolation.
- Physical board/flash/SoC identification, serial access and a tested recovery procedure.
- A supported custom-firmware build or acceptance of modified firmware.

Authenticated Telnet survives reboot and local streaming works on the tested stock-firmware camera. Longer streaming sessions, physical power cycles and the other items above still need testing before relying on it unattended.
