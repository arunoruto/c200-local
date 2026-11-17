+++
title = "How it works"
description = "The saved configuration hook, account layout, Live555 discovery, firewall and NTP."
weight = 10
+++

For the actual commands and order, start with [the permanent Telnet guide](../guide/permanent-telnet.md). This page explains why that procedure works and records the diagnostics.

This describes the installed experiment on exact C200 V2 1.1.15. It requires an existing authorized root shell and is not a general-purpose deployment script. IP addresses in examples use `192.168.1.100`; the test camera's identifiers and configuration are not distributed.

## Hardware and firmware scope

| Item | Tested or observed |
|---|---|
| Camera | Tapo C200, hardware 2.0, EU suffix 4555 |
| Previous build | 1.3.17 Build 260112 Rel.58281n(4555) |
| Running build | 1.1.15 Build 211112 Rel.10589n(4555) |
| Platform | Expected Realtek RTS3903N, RLX/Lexra MIPS; board markings unverified |
| Sensor | SC2336 reported by the API; physical identification unverified |
| Usable RAM | 40,524 KiB reported by Linux |

The unmodified stock images were traced offline before the normal downgrade. Exposed hardware/OEM/vendor/zone matches, package checks and later same-device running-version reads are distinct evidence. A similarly named C200 profile for an Ingenic platform is not a compatible Realtek firmware port. A GPL archive and plaintext SquashFS do not establish a complete build or recovery environment.

## Why ordinary filesystem edits disappeared

The writable root/overlay is RAM-backed. Boot restores user configuration from flash into `/tmp/etc/uc_conf`, reached through `/etc/config`. Editing an init script or placing a file in the ordinary overlay does not by itself make that file survive a reboot.

The exact vendor `uc_convert` routing identifies mode 0 as configuration restore and mode 1 as configuration save. The save includes regular files beneath the configuration tree and writes a 64 KiB user-configuration area. File-only experiments and physical readback confirmed that added bootstrap files survived the real save/restore path.

**Ordinary `uci commit` can also save flash.** Earlier research incorrectly treated it as reliably RAM-only. Approved NTP commits changed the configuration partition, and the exact stock `libuci.so` contains the vendor saver invocation `uc_convert -t 1`. Treat commits as persistence operations and retain backups. No encryption implementation was inspected or modified to test the format.

## The saved firewall startup hook

The stock firewall reads UCI IP-control endpoints, concatenates them into a generated shell script, then sources it. Its semicolon stripping does not remove command substitution. On this build, `S45firewall` reaches that path during startup.

The relevant vendor source paths in the extracted image are:

- `lib/firewall/core_ipctrl.sh`: reads blacklist/whitelist endpoints.
- `lib/firewall/fw.sh`: generates shell text.
- `lib/firewall/core.sh`: sources it and selects IP-control handling.

The first probe used a private scratch UCI directory, stubbed both iptables commands and wrote a harmless scratch marker. Control/test cases and unchanged real firewall/partition checks established the interpretation path without restarting production networking.

The installed hook uses a blacklist section whose actual IP range is confined to documentation address `203.0.113.254`. Its endpoint contains a shell invocation of the saved launcher. The bootstrap files live at `/etc/config/local_access/launch.sh` and `boot.sh`. Configuration encryption is left opaque; the normal vendor tools handle persistence.

The launcher backgrounds the worker with all descriptors redirected so firewall startup can finish. The worker uses a RAM lock, validates the account layout, assembles the egress chain before attaching it, waits a bounded time for the fixed LAN address and starts one Telnet listener with `/bin/login`. Repeated direct launches retained the same listener. Repeated full stock firewall reloads remain untested.

The bootstrap protects its configuration/runtime directories, accepts restored scripts without executable bits by invoking a shell, and respects a disable marker. It does not run a downloaded script or change a firmware executable.

## The account-layout bug and correction

The first installed bootstrap assumed that root always used `/etc/shadow`. Its test fixture modeled the modified runtime environment, but the stock boot placed the root hash directly in `/etc/passwd`. Files and hook survived the first reboot; the account guard prevented the listener from starting. The owner recovered a temporary network shell.

The corrected bootstrap accepts either an enabled direct hash or an enabled shadow-backed account. It rejects empty/locked account hashes and **never writes `/etc/passwd` or `/etc/shadow`**. No saved root-hash file is required. Device-free fixtures covered direct/shadow/empty/locked layouts; fresh live login, empty-password refusal and post-reboot account checksums passed.

Telnet binds the selected LAN address on 2323 and uses the existing stock password. It is plaintext on the LAN. DHCP changes can prevent this fixed bind; that behavior has not been tested. Editing the local password file on the research computer did not change the device password.

## Final IPv4 egress policy

The `TAPO_LOCAL_ONLY` chain is attached at the start of OUTPUT. Rules are ordered as follows:

| Match | Action and purpose |
|---|---|
| Output through loopback | Return; preserve local IPC |
| Destination 228.67.43.91, UDP source 15947 and destination 15947 | Return; Live555 local-address probe |
| Destination 162.159.200.1, UDP destination 123 | Return; approved Cloudflare NTP |
| UDP/TCP destination 53 | Drop; deny DNS, including forwarding through a LAN resolver |
| Destination selected LAN subnet | Return; local clients/services |
| Destination 239.255.255.250, UDP destination 3702 | Return; ONVIF discovery |
| Destination 255.255.255.255, UDP 68→67 | Return; DHCP broadcast |
| Everything else | Drop |

“Return” continues into the existing OUTPUT rules. There is no broad established-connection exception that preserves old cloud flows. Packet counters showed denied DNS and other external attempts while fresh local sessions worked. Stock cloud processes continue trying; they were not removed from the firmware.

This is IPv4 enforcement on the camera. IPv6 and an upstream startup packet capture were not validated. The hook's observed startup behavior does not establish a gap-free egress boundary across every boot phase. Full firewall restarts can clear custom chains and were not used as harmless diagnostics.

## The RTSP discovery trap

The isolated boot initially produced this sequence:

1. OPTIONS 200.
2. DESCRIBE 401 challenge.
3. Invalid credentials: another 401 promptly.
4. Valid credentials: DESCRIBE stalled; no RTP.

Independent FFmpeg tests reproduced the stall. Sensor/encoder diagnostics showed advancing raw frames at 15 fps. Clock correction, normal media callbacks and a temporary ordinary media-encryption setting test did not resolve it. The encryption setting was restored ON before the final save.

The stock `cet` binary contains Live555's multicast/local-address strings. In the [released implementation](https://nest-open-source.googlesource.com/nest-cam/4320010/live555/+/c98cf70995ccdb2054765a8a14f8a0d12f245681/live555/groupsock/GroupsockHelper.cpp), `ourIPAddress()` discovers its source address with a TTL-zero `hostIdTest` datagram to 228.67.43.91, UDP 15947 at both ends. Failure falls back to resolving the host name. The policy blocked both paths.

One exact rule restored DESCRIBE/SETUP/PLAY/RTP without restarting a service. Its counter advanced by one 39-byte datagram. The earlier warm-boot isolation test had worked because the local address could already be cached; the new boot exposed the initialization dependency. That caching explanation is an inference supported by the code and observed behavior.

After persistence and reboot, independent decoding yielded 75 H.264 frames from each stream over five-second intervals:1920×1080 and 640×360. Probe counts include startup behavior and are not a sustained performance benchmark. No images, video or audio were saved.

## Time synchronization

The camera initially had a 2021 clock and no normal time-sync marker. A trusted-host time correction and a later real NTP sync did not independently fix RTSP.

The final policy permits only Cloudflare 162.159.200.1 UDP/123 as an external unicast time source. Vendor UCI peer lists inherited/appended default names even with an empty override, so DNS blocking delayed the stock client's first synchronization. The bootstrap starts one detached literal-peer `ntpd -n -q -p 162.159.200.1` per boot when the normal marker is absent. It quits after synchronization; the ordinary stock client remains in place. A real synchronization and `/tmp/time_sync` were verified after reboot.

The provider address is documented by [Cloudflare](https://developers.cloudflare.com/time-services/ntp/usage/). Google NTP was considered but not mixed with Cloudflare's time service.

## Watchdog and ONVIF

An earlier RAM-only watchdog experiment retained monitoring of seven local services while cloud daemons were stopped. It passed bounded warm-session checks but did not solve the isolated-boot RTSP stall. That modification was lost on reboot. The final installed result uses the stock watchdog and running stock cloud services behind the filter.

ONVIF was checked read-only after the successful reboot. `GetCapabilities`, `GetProfiles` and `GetStreamUri` returned HTTP 200 without SOAP faults. Two profiles advertised `/stream1` and `/stream2` on RTSP 554. The device advertised `http://CAMERA_IP:2020/onvif/service`; TCP 2020 and UDP 3702 belonged to `nvid`. A direct unicast WS-Discovery probe received a ProbeMatch. Multicast discovery across the remote subnet route was not tested. No PTZ or configuration request was sent.

See [validation](validation.md) for save/readback/reboot acceptance and remaining work.
