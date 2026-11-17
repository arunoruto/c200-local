+++
title = 'Before you start'
description = 'Get the project, identify the tested hardware and prepare the accounts, addresses and backups.'
weight = 5
+++

This guide follows a specific path: stock **C200 hardware V2**, from **1.3.17 Build 260112 Rel.58281n(4555)** to **1.1.15 Build 211112 Rel.10589n(4555)**, then persistent authenticated Telnet with local RTSP and ONVIF.

## Get the project

On your computer, install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
git clone https://github.com/arunoruto/c200-local.git
cd c200-local
uv sync --locked --group analysis
```

The project pins Python 3.13; uv manages the project environment. Run the host commands from this repository directory. The scripts prompt for passwords rather than accepting them in command arguments.

## Check the camera and accounts

| Item | What you need |
|---|---|
| Hardware/build | Confirm C200 V2 and the tested source firmware through normal device information |
| Firmware operation | Normal owner/admin access; a streaming-only login may not have update privileges |
| RTSP and ONVIF | A working Camera Account, kept separate from the owner login |
| Persistence | An existing authorized Linux root shell after the downgrade |
| Network | A known camera address and a fixed DHCP reservation for the eventual listener |
| Recovery | Stable power, private off-device backups and a recovery plan |

Do not infer compatibility from the product name alone. Other C200 hardware revisions, OEM variants and firmware builds are not covered by the live result. Matching compatibility fields is a precheck, not a guarantee of boot success.

Initial shell access is covered only by the [linked external references](initial-shell.md). This project does not reproduce those instructions or claim that every referenced method applies to every build.

## Use the right machine and address

The guide labels commands as **host** or **camera**. Host commands run on your computer; camera commands run inside your existing root shell.

| Example | Meaning |
|---|---|
| `192.168.1.100` | Camera's reserved LAN address |
| `192.168.1.10` | Computer serving the public bootstrap files |
| `192.168.1.0/24` | LAN subnet permitted by the example filter |

Replace these examples with your own values. Keep the literal protocol destinations 228.67.43.91/UDP 15947, 239.255.255.250/UDP 3702 and Cloudflare 162.159.200.1/UDP 123 as described in the firewall policy.

For remote access, the experiment used an existing Tailscale subnet router. No Tailscale agent was installed on the camera. A camera cannot necessarily reach a remote computer's file server just because your computer can connect to the camera; the file-transfer example requires that return path.

## Know the write boundaries

The firmware uploader's default invocation checks request construction offline. Its explicit `--attempt` sends the firmware request; acceptance starts the stock updater automatically.

The persistence trial stages files in the running configuration tree. The later `uci commit` and `uc_convert -t 1` commands are real persistence operations. On this firmware, even ordinary `uci commit` can save flash. Copy backups off-device before crossing that boundary; `/tmp` disappears on reboot.

No public firmware or device dump is included in the repository. The reference downloader verifies the stock image against its pinned size and SHA-256.

## Follow the sequence

1. [Downgrade and verify the running version](downgrade.md).
2. Use the [external initial-shell references](initial-shell.md) for the root prerequisite.
3. [Stage, test and save permanent Telnet](permanent-telnet.md).
4. [Verify both streams, ONVIF, local API, time and authentication](verify-streams.md).

If a check fails, use [troubleshooting](troubleshooting.md) before repeating any write or reboot.
