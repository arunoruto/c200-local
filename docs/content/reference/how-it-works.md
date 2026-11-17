+++
title = "How it works"
description = "The saved configuration hook, account layout, Live555 discovery, firewall and NTP."
weight = 10
+++

Follow [the permanent Telnet guide](../guide/permanent-telnet.md) for installation. The sections below explain the startup hook, firewall rules and streaming fix.

The setup was tested on C200 V2 stock 1.1.15 and needs an existing root shell. Review other firmware separately before adapting it. The examples use `192.168.1.100`; the test camera's identifiers and configuration stay private.

## Hardware and firmware scope

| Item | Tested or observed |
|---|---|
| Camera | Tapo C200, hardware 2.0, EU suffix 4555 |
| Previous build | 1.3.17 Build 260112 Rel.58281n(4555) |
| Running build | 1.1.15 Build 211112 Rel.10589n(4555) |
| Platform | Expected Realtek RTS3903N, RLX/Lexra MIPS; board markings unverified |
| Sensor | SC2336 reported by the API; physical identification unverified |
| Usable RAM | 40,524 KiB reported by Linux |

The unmodified stock images were analyzed offline before the downgrade. Hardware/OEM/vendor/zone matches checked compatibility, package checks examined the image, and later version reads from the same camera confirmed the running firmware.

A similarly named C200 profile for an Ingenic platform is not compatible with this Realtek camera. Having a GPL archive and a readable SquashFS image does not provide a complete firmware build or recovery environment.

## Why ordinary filesystem edits disappeared

The writable root/overlay is RAM-backed. Boot restores user configuration from flash into `/tmp/etc/uc_conf`, reached through `/etc/config`. Editing an init script or placing a file in the ordinary overlay does not by itself make that file survive a reboot.

The stock `uc_convert` utility uses mode 0 to restore configuration and mode 1 to save it. The save includes regular files beneath the configuration tree and writes a 64 KiB user-configuration area. File-only experiments and physical readback confirmed that added bootstrap files survived the real save/restore path.

**Ordinary `uci commit` can also save flash.** The initial investigation mistakenly treated it as RAM-only. Committing NTP settings changed the configuration partition, and the stock `libuci.so` contains a call to `uc_convert -t 1`. Back up configuration before committing changes. These tests used the vendor tools without inspecting or modifying the configuration-encryption implementation.

## The saved firewall startup hook

The stock firewall reads UCI IP-control endpoints, concatenates them into a generated shell script, then sources it. Its semicolon stripping does not remove command substitution. On this build, `S45firewall` reaches that path during startup.

The relevant vendor source paths in the extracted image are:

- `lib/firewall/core_ipctrl.sh`: reads blacklist/whitelist endpoints.
- `lib/firewall/fw.sh`: generates shell text.
- `lib/firewall/core.sh`: sources it and selects IP-control handling.

The first test used a temporary UCI directory and simulated both iptables commands. The injected command wrote a temporary marker file. Comparing runs with and without the hook showed that the generated script ran the command, while checks confirmed the real firewall and flash partitions were unchanged. No network restart was needed.

The installed hook uses a blacklist section whose actual IP range is confined to documentation address `203.0.113.254`. Its endpoint contains a shell invocation of the saved launcher. The bootstrap files live at `/etc/config/local_access/launch.sh` and `boot.sh`. The vendor tools save and restore the configuration without changes to its encryption.

The launcher starts the worker in the background and redirects its input and output so firewall startup can finish. The worker uses a lock in RAM, checks the root account, builds the filter before attaching it, waits for the fixed LAN address and starts one Telnet listener with `/bin/login`. The address wait has a timeout. Launching it again kept the same listener running. Repeated full firewall reloads have not been tested.

The startup scripts restrict access to their configuration and runtime directories, run restored files through a shell even if executable permissions are missing, and check the disable marker. At boot, they use the saved local files without downloading code or changing a firmware executable.

## The account-layout bug and correction

The first installed bootstrap assumed that root always used `/etc/shadow`. Its test fixture modeled the modified runtime environment, but the stock boot placed the root hash directly in `/etc/passwd`. Files and hook survived the first reboot; the account guard prevented the listener from starting. A temporary network shell was used to recover access.

The corrected bootstrap accepts either an enabled direct hash or an enabled shadow-backed account. It rejects empty/locked account hashes and **never writes `/etc/passwd` or `/etc/shadow`**. No saved root-hash file is required. Tests on a computer covered direct-hash, shadow-backed, empty and locked accounts. The camera then passed fresh login, empty-password refusal and account-checksum checks after reboot.

Telnet binds the selected LAN address on 2323 and uses the existing stock password. It is plaintext on the LAN. DHCP changes can prevent this fixed bind; that behavior has not been tested. A password file kept on the computer only supplies login credentials; editing it does not change the camera's password.

## Final IPv4 egress policy

The `TAPO_LOCAL_ONLY` chain is attached at the start of OUTPUT. Rules are ordered as follows:

| Match | Action and purpose |
|---|---|
| Output through loopback | Return; preserve local IPC |
| Destination 228.67.43.91, UDP source 15947 and destination 15947 | Return; Live555 local-address probe |
| Destination 162.159.200.1, UDP destination 123 | Return; Cloudflare NTP |
| UDP/TCP destination 53 | Drop; deny DNS, including forwarding through a LAN resolver |
| Destination selected LAN subnet | Return; local clients/services |
| Destination 239.255.255.250, UDP destination 3702 | Return; ONVIF discovery |
| Destination 255.255.255.255, UDP 68→67 | Return; DHCP broadcast |
| Everything else | Drop |

"Return" continues into the existing OUTPUT rules. There is no broad established-connection exception that preserves old cloud flows. Packet counters showed denied DNS and other external attempts while fresh local sessions worked. Stock cloud processes continue trying; they were not removed from the firmware.

The filter covers IPv4 traffic from the camera. IPv6 was not tested, and no upstream packet capture covered startup, so traffic before the hook runs remains unverified. Full firewall restarts can clear custom chains and were avoided during diagnostics.

## The RTSP discovery trap

The isolated boot initially produced this sequence:

1. OPTIONS 200.
2. DESCRIBE 401 challenge.
3. Invalid credentials: another 401 promptly.
4. Valid credentials: DESCRIBE stalled; no RTP.

Independent FFmpeg tests reproduced the stall. Sensor/encoder diagnostics showed advancing raw frames at 15 fps. Correcting the clock, invoking the normal media callbacks and temporarily changing the media-encryption setting did not fix it. The encryption setting was restored ON before the final save.

The stock `cet` binary contains Live555's multicast/local-address strings. In the [released implementation](https://nest-open-source.googlesource.com/nest-cam/4320010/live555/+/c98cf70995ccdb2054765a8a14f8a0d12f245681/live555/groupsock/GroupsockHelper.cpp), `ourIPAddress()` discovers its source address with a TTL-zero `hostIdTest` datagram to 228.67.43.91, UDP 15947 at both ends. Failure falls back to resolving the host name. The policy blocked both paths.

One exact rule restored DESCRIBE/SETUP/PLAY/RTP without restarting a service. Its counter advanced by one 39-byte datagram. The earlier test applied isolation while the camera was already running and streaming still worked. The likely explanation is that Live555 had already cached its local address. After a new boot it needed to discover that address again. The released code and observed behavior fit this explanation, but do not prove it.

After persistence and reboot, an independent decoding test produced 75 H.264 frames from each stream over five-second intervals: 1920×1080 and 640×360. Probe counts include startup behavior and are not a sustained performance benchmark. No images, video or audio were saved.

## Time synchronization

The camera initially had a 2021 clock and no normal time-sync marker. A trusted-host time correction and a later real NTP sync did not independently fix RTSP.

The final policy permits only Cloudflare 162.159.200.1 UDP/123 as an external unicast time source. Vendor UCI peer lists inherited/appended default names even with an empty override, so DNS blocking delayed the stock client's first synchronization. The bootstrap starts one detached literal-peer `ntpd -n -q -p 162.159.200.1` per boot when the normal marker is absent. It quits after synchronization; the ordinary stock client remains in place. A real synchronization and `/tmp/time_sync` were verified after reboot.

The provider address is documented by [Cloudflare](https://developers.cloudflare.com/time-services/ntp/usage/). Google NTP was considered but not mixed with Cloudflare's time service.

## Watchdog and ONVIF

An earlier RAM-only watchdog test kept monitoring seven local services while the cloud daemons were stopped. Short checks passed while the camera was running, but the change did not fix RTSP stalling after an isolated boot and was lost on reboot. The final setup keeps the stock watchdog and cloud services running behind the filter.

ONVIF was checked read-only after the successful reboot. `GetCapabilities`, `GetProfiles` and `GetStreamUri` returned HTTP 200 without SOAP faults. Two profiles advertised `/stream1` and `/stream2` on RTSP 554. The device advertised `http://CAMERA_IP:2020/onvif/service`; TCP 2020 and UDP 3702 belonged to `nvid`. A direct unicast WS-Discovery probe received a ProbeMatch. Multicast discovery across the remote subnet route was not tested. No PTZ or configuration request was sent.

See the [test results](validation.md) for the save, readback and reboot checks, along with what remains untested.
