+++
title = 'Verify local services'
description = 'Check both RTSP streams, ONVIF, the local API, the clock and the saved listener after reboot.'
weight = 40
+++

Use this checklist before changing the camera, during the RAM trial with the filter attached, and after the [persistence procedure](permanent-telnet.md). Check with **new connections** each time. All addresses below are examples. Use your actual fixed camera address.

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

## Check the listener and local API

Open `telnet 192.168.1.100 2323` after the trial starts and again after reboot. Log in as Linux root with the existing password and run `id`. In a separate connection, confirm an empty password is refused. Keep your original root connection open during the trial.

To check the local API with a new connection, run this on the **host** from the repository root. Substitute your Camera Account username:

```sh
uv run --locked python scripts/read_camera_info.py --host 192.168.1.100 --username camera-user --firmware work/downloads/c200v2-1.1.15.bin --output private/service-check.json
```

Use a new output filename on each run; existing reports are not overwritten. Confirm the same device and expected running build in the private report. An exposed-field match alone is not a complete service check. Before installation, use your existing shell: port 2323 need not exist yet.

## Check the actual video

Open each RTSP path in your player or NVR, using the existing Camera Account. Confirm that frames keep arriving on both streams after reboot, with the OUTPUT filter attached.

Select **RTSP over TCP** in your player or NVR to match the tested setup. UDP media transport has not been tested separately.

The final decoding test produced:

| Stream | Codec | Resolution | Frames in the five-second probe |
|---|---|---|---:|
| stream1 | H.264 | 1920 × 1080 | 75 |
| stream2 | H.264 | 640 × 360 | 75 |

No media was saved during testing. These short checks do not show how the streams perform over long sessions.

{{< callout type="info" >}}
An open port or `OPTIONS 200` does not confirm working video. With the cloud blocked, the camera initially passed both checks after boot, then stalled on authenticated DESCRIBE. The Live555 multicast exception restored DESCRIBE, SETUP, PLAY and RTP.
{{< /callout >}}

## Confirm the filter, time and encryption

From the **camera** root shell during the trial and after reboot:

```sh
iptables -S OUTPUT
iptables -S TAPO_LOCAL_ONLY
iptables -nvxL TAPO_LOCAL_ONLY
date -u
test -e /tmp/time_sync
uci -q get cet.media_encrypt.enabled
```

Confirm the first OUTPUT rule jumps to `TAPO_LOCAL_ONLY`, the exact Live555/ONVIF exceptions and final DROP are present, and the LAN subnet matches your clients. The clock should synchronize and encryption should read `on`. Recheck fresh video/API sessions after at least 180 seconds of uptime. The pre-change baseline may have no custom chain or sync marker; do not change encryption to make the trial pass.

The attached filter and its drop counters show camera-side IPv4 filtering. IPv6 isolation and traffic during early boot have not been verified.

## Check ONVIF

Add the camera by IP and port **2020** in your ONVIF client/NVR, with the Camera Account. List both profiles, get their stream URIs, then open those RTSP streams on 554. ONVIF is the control/discovery protocol; video still travels over RTSP.

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

Compare account and bootstrap checksums with the private baseline. Check that an empty password is refused in another login. Repeat fresh API/RTP checks beyond 180 seconds uptime to pass the first watchdog scan.

Stock watchdog and cloud processes remain running behind the IPv4 filter. You can leave those processes and the watchdog unchanged.

If a check fails, use [troubleshooting](troubleshooting.md) to isolate the stage before repeating a write or restart.

## What this proves

The camera passed these checks after a normal reboot, over the short intervals described above. Long streaming, physical power cycling, IPv6 enforcement, upstream startup capture, DHCP address changes, full firewall reloads, audio, recording, PTZ and IR transitions remain unverified. Review the [validation record](../reference/validation.md) and [how it works](../reference/how-it-works.md) before extending the experiment.
