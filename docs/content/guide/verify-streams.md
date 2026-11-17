+++
title = 'Verify local services'
description = 'Check both RTSP streams, ONVIF, the local API, the clock and the saved listener after reboot.'
weight = 40
+++

After the [persistence procedure](permanent-telnet.md), check with **new connections**. All addresses below are examples. Use your actual fixed camera address.

## Connection details

| Service | Address or port | Login |
|---|---|---|
| Main RTSP | `rtsp://192.168.1.100:554/stream1` | Camera Account |
| Secondary RTSP | `rtsp://192.168.1.100:554/stream2` | Camera Account |
| ONVIF control | TCP **2020**, advertised path `/onvif/service` | Camera Account |
| ONVIF discovery | UDP **3702**, group `239.255.255.250` | Discovery |
| Local HTTPS API | TCP **443** | Normal supported local account |
| Persistent Telnet | TCP **2323**, fixed LAN bind | Linux root/password |

The Camera Account is separate from both the cloud owner account and Linux root. Enter credentials through the client's normal login fields; avoid putting passwords into command arguments or logs.

## Check the actual video

Open each RTSP path in your player or NVR, using the existing Camera Account. Confirm that frames keep arriving on both streams after reboot, with the OUTPUT filter attached.

The final independent probe decoded:

| Stream | Codec | Resolution | Frames in the five-second probe |
|---|---|---|---:|
| stream1 | H.264 | 1920 × 1080 | 75 |
| stream2 | H.264 | 640 × 360 | 75 |

No media was saved in the experiment. These are short probes, not a sustained performance benchmark.

{{< callout type="info" >}}
An open port or `OPTIONS 200` is insufficient. The broken isolated-boot state passed both, then stalled on authenticated DESCRIBE. The exact Live555 multicast exception restored DESCRIBE, SETUP, PLAY and RTP.
{{< /callout >}}

## Check ONVIF

Add the camera by IP and port **2020** in your ONVIF client/NVR, with the Camera Account. Enumerate both profiles, retrieve their stream URIs, then open those RTSP streams on 554. ONVIF is the control/discovery protocol; video still travels over RTSP.

The tested camera advertised `http://192.168.1.100:2020/onvif/service` with its actual address in place of the example. Authenticated `GetCapabilities`, `GetProfiles` and `GetStreamUri` returned 200 without SOAP faults. A direct unicast WS-Discovery probe also received a ProbeMatch. Multicast discovery across the remote subnet route was not tested.

No PTZ or configuration request was needed for these checks. See the [TP-Link RTSP/ONVIF guide](https://www.tp-link.com/us/support/faq/2680/) for the standard client setup.

## Check the saved listener, policy and time

From a fresh Linux root login on 2323:

```sh
id
cat /proc/uptime
cat /tmp/tapo-local-access/bootstrap.log
iptables -S OUTPUT
iptables -nvxL TAPO_LOCAL_ONLY
date -u
test -e /tmp/time_sync
uci -q get cet.media_encrypt.enabled
```

The OUTPUT chain should be attached, DNS/other external DROP counters should increase, the clock should be synchronized, and media encryption should remain `on`. The allowed public unicast time source is Cloudflare `162.159.200.1`, UDP 123. The local multicast probe and ONVIF/DHCP exceptions remain present.

Compare account and bootstrap checksums with the private baseline. Explicitly check empty-password refusal in another login. Repeat fresh API/RTP checks beyond 180 seconds uptime to pass the first watchdog scan.

Stock watchdog and cloud processes remain running behind the IPv4 filter. The installed solution does not require stopping them or modifying the watchdog.

## What this proves

The final camera passed these bounded checks after a normal reboot. Long streaming, physical power cycling, IPv6 enforcement, upstream startup capture, DHCP address changes, full firewall reloads, audio, recording, PTZ and IR transitions remain unverified. Review the [validation record](../reference/validation.md) and [how it works](../reference/how-it-works.md) before extending the experiment.
