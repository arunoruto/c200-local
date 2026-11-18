+++
title = "Make it local"
description = "Block cloud traffic while keeping LAN streaming, ONVIF, local control and time synchronization working."
weight = 30
+++

The goal is to use the camera from your LAN with the Tapo cloud blocked: watch both RTSP streams, connect an ONVIF client or NVR, read the local API, and keep root access after reboot.

On the tested **C200 V2 stock 1.1.15**, this works by saving an IPv4 firewall policy on the camera. The same startup scripts restore that policy and start authenticated Telnet at boot. This page explains the local-operation setup; the [permanent Telnet guide](permanent-telnet.md) contains the backup, trial and save commands for installing both together.

## What the system exploration found

| Part of the system | Finding |
|---|---|
| RTSP | The stock media service, `cet`, can serve both streams with cloud traffic blocked |
| ONVIF | `nvid` handles TCP 2020 and UDP 3702; profiles, stream URIs and unicast discovery worked after reboot |
| Watchdog and cloud services | The final setup keeps the stock processes running behind the filter; an earlier temporary shutdown did not solve the RTSP stall |
| Startup and configuration | The writable overlay is RAM-backed, but user configuration can save the startup scripts and firewall hook for the next boot |
| Streaming dependency | Live555 needs a multicast local-address probe during initialization; blocking it made authenticated RTSP requests stall |

The [technical explanation](../reference/how-it-works.md) describes the firmware and runtime investigation. The [test record](../reference/validation.md) lists the successful checks, earlier failures and untested features.

## What stays local and what is blocked

The startup script builds `TAPO_LOCAL_ONLY` and attaches it as the first rule in the camera's IPv4 OUTPUT chain. It filters traffic leaving the camera in this order:

| Traffic | Rule and purpose |
|---|---|
| Loopback | Allow local communication between camera services |
| UDP to 228.67.43.91, source and destination port 15947 | Allow Live555 to discover the camera's local address for RTSP |
| UDP to 162.159.200.1, destination port 123 | Allow Cloudflare NTP for clock synchronization |
| UDP or TCP destination port 53 | Drop DNS requests, including requests to a LAN resolver |
| Destination LAN subnet | Allow replies to local streaming, ONVIF, API and Telnet clients |
| UDP to 239.255.255.250, destination port 3702 | Allow ONVIF discovery |
| UDP to 255.255.255.255, source 68 and destination 67 | Allow DHCP broadcasts |
| All other IPv4 traffic | Drop |

The allow rules use `RETURN`, so matching traffic continues through the existing OUTPUT rules. The script builds the full chain before attaching it. It does not keep old cloud connections alive through a broad established-connection exception.

The LAN subnet in `camera/boot.sh` is an example. Set it to your network, along with the camera's fixed address. A remote client outside that subnet needs a suitable route and source NAT as described in [the routing notes](getting-started.md#use-the-right-machine-and-address).

**Cloudflare NTP is an external exception.** Local streaming and control use the LAN, but the tested policy still lets the camera contact that public time server. A completely offline setup or a replacement LAN NTP server has not been validated here.

## Keep the rule that RTSP needs

A blanket WAN/DNS block initially left port 554 open and RTSP OPTIONS working, but authenticated DESCRIBE stalled after boot. The camera needed this exact rule before the drops:

```text
-d 228.67.43.91 -p udp --sport 15947 --dport 15947 -j RETURN
```

Adding it restored DESCRIBE, SETUP, PLAY and RTP without restarting a service. Keep this rule, the ONVIF discovery allowance and the LAN return when adapting the script. Correcting the clock or temporarily changing the media-encryption setting did not fix the stall. Leave media encryption on.

## Install the policy and save it for boot

Start with the [downgraded firmware](downgrade.md), an [existing root shell](initial-shell.md), working Camera Account credentials, and a fixed DHCP reservation for the camera.

Then follow the [permanent Telnet installation](permanent-telnet.md) once, in order:

1. Record the current state and copy private backups off the camera.
2. Adapt the addresses in the startup script and copy both scripts into the RAM configuration tree.
3. Run the timed rollback trial. The worker installs the filter before starting the Telnet listener. Check actual video from both streams, ONVIF, the API and a fresh root login while the filter is attached.
4. Only after those checks pass, save the startup hook and configuration using the documented commands. Both `uci commit` and the vendor saver can write flash.
5. Reboot once and repeat the checks with new connections, including another check after at least 180 seconds of uptime.

If you already completed that installation, the same scripts already include the local-operation policy. Use the read-only checks below instead of installing another chain or repeating the save. There is no separate cloud-blocking deployment to run afterward.

## Check that local operation is working

From the **camera's root shell**, inspect the installed rules and counters:

```sh
iptables -S OUTPUT
iptables -S TAPO_LOCAL_ONLY
iptables -nvxL TAPO_LOCAL_ONLY
```

Confirm the first OUTPUT rule jumps to `TAPO_LOCAL_ONLY`, the complete rule set above is present in order, and the final rule drops the remaining traffic. DNS and external DROP counters should increase as stock cloud processes try to connect. A missing chain or jump means the camera-side policy is not active.

Use the [service checklist](verify-streams.md) to confirm, while that filter is attached:

- Actual authenticated video from both `/stream1` and `/stream2`, using RTSP over TCP.
- ONVIF profiles and stream URIs on TCP 2020, plus discovery where your network supports it.
- A fresh authenticated local API request and password login on Telnet 2323.
- Accurate time, the sync marker and media encryption still `on`.

An open port or increasing DROP counter alone is not a complete check. The tested camera decoded 75 frames from each stream over five-second intervals after reboot, and ONVIF capabilities, profiles, stream URIs and unicast discovery passed.

## Limits of the current setup

The camera keeps its stock firmware, cloud processes and watchdog. Cloud connection attempts continue behind the filter. Stopping those services or replacing the firmware would need further work on their dependencies.

The filter covers IPv4. IPv6 and traffic before the startup hook runs have not been verified. Strict isolation throughout boot would need an upstream policy covering both IP versions and a startup packet capture to validate it; that has not been tested here.

Long streaming sessions, repeated physical power cycles, full firewall reloads, DHCP address changes, audio, recording, PTZ and IR transitions also remain unverified. A full stock firewall restart can remove the custom rules. Review the [test limits](../reference/validation.md#still-unverified) before relying on the setup unattended.
