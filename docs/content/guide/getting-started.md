+++
title = 'Before you start'
description = 'Get the project, identify the tested hardware and prepare the accounts, addresses and backups.'
weight = 5
+++

This guide covers the tested setup: stock **C200 hardware V2**, from **1.3.17 Build 260112 Rel.58281n(4555)** to **1.1.15 Build 211112 Rel.10589n(4555)**, then persistent authenticated Telnet with local RTSP and ONVIF.

## Get the project

On your computer, install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
git clone https://github.com/arunoruto/c200-local.git
cd c200-local
uv sync --locked --group analysis
```

Also have a Telnet client and an RTSP player/ONVIF client or NVR ready on your computer. These are separate applications; `uv sync` installs the project's Python dependencies, not those clients. Use the player and ONVIF client to confirm both streams and profiles before changing the camera.

The project uses Python 3.13, managed by uv. Run host commands from this repository directory. The scripts prompt for passwords so you can keep them out of command arguments.

## Check the camera and accounts

| Item | What you need |
|---|---|
| Hardware/build | Confirm C200 V2 and the tested source firmware through normal device information |
| Firmware operation | Normal owner/admin access; a streaming-only login may not have update privileges |
| RTSP and ONVIF | A working Camera Account, kept separate from the owner login |
| Persistence | A Linux root shell on the camera after the downgrade |
| Network | A known camera address and a fixed DHCP reservation for Telnet |
| Recovery | Stable power, private off-device backups and a recovery plan |

Check the hardware revision and build, even if the product name matches. Other C200 revisions, OEM variants and firmware builds have not been tested. Matching compatibility fields is required before uploading, but cannot guarantee that the camera will boot.

Use the [external shell-access guides](initial-shell.md) to get the root shell. Check their firmware requirements; a method for one build may not work on another. If the method uses a reverse connection, [prepare the host listener and firewall](initial-shell.md#prepare-the-listener-and-firewall) first so the camera can connect back to your computer.

## Use the right machine and address

The guide labels commands as **host** or **camera**. Host commands run on your computer; camera commands run inside your existing root shell.

| Example | Meaning |
|---|---|
| `192.168.1.100` | Camera's reserved LAN address |
| `192.168.1.10` | Computer serving the public bootstrap files |
| `192.168.1.0/24` | LAN subnet permitted by the example filter |

Replace these examples with your own values. Keep the literal protocol destinations 228.67.43.91/UDP 15947, 239.255.255.250/UDP 3702 and Cloudflare 162.159.200.1/UDP 123 as described in the firewall policy.

The example filter permits replies to clients in the selected LAN subnet. For routed or VPN access, the camera must see the connection as coming from that permitted subnet, for example through a subnet router that performs source NAT. Replies to a remote client address outside it will be dropped. Do the first trial from the same LAN if that routing is uncertain.

For remote access, the experiment used an existing Tailscale subnet router. No Tailscale agent was installed on the camera. A camera cannot necessarily reach a remote computer's file server just because your computer can connect to the camera; the file-transfer example requires that return path.

## Know when commands write to flash

By default, the firmware uploader checks the image and upload request offline. Adding `--attempt` sends the request to the camera. If accepted, it starts the stock updater automatically.

The first Telnet trial keeps the new files in RAM. The later `uci commit` and `uc_convert -t 1` commands save configuration to flash. On this firmware, even ordinary `uci commit` can write flash. Copy backups off the camera before saving; `/tmp` disappears on reboot.

No public firmware or device dump is included in the repository. The reference downloader verifies the stock image against its pinned size and SHA-256.

## Follow the sequence

1. [Downgrade and verify the running version](downgrade.md).
2. Get a root shell using the [external shell-access guides](initial-shell.md).
3. [Read how to make the camera local](make-it-local.md): the cloud-blocking policy, streaming exceptions and test limits.
4. [Stage, test and save the policy with permanent Telnet](permanent-telnet.md).
5. [Verify both streams, ONVIF, local API, time and authentication](verify-streams.md).

If a check fails, use [troubleshooting](troubleshooting.md) before repeating any write or reboot.
