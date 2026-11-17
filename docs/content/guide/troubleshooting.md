+++
title = 'Troubleshooting'
description = 'Identify the failing stage without blindly repeating firmware writes, restarts or configuration saves.'
weight = 50
+++

Start with the stage that failed. A successful TCP connection, HTTP upload response or RTSP OPTIONS response establishes less than a successful authenticated session and video after boot.

## Firmware upload disconnects or times out

Do not automatically resubmit. The stock handler stops services before receiving the whole image, and the updater can close management connections. The public uploader intentionally sends once and never retries a firmware POST.

Honor the returned wait interval. When management returns, collect fresh device information and compare the same-device running version with the private baseline. HTTP200 with `error_code:0` means accepted, not completed. See [the upload and timeout record](downgrade.md#why-the-timeout-matters).

In the experiment a 15-second timeout disconnected; a separately initiated request with 120 seconds was accepted. Both socket timeouts in the public uploader are 120 seconds. A new timeout is still ambiguous, not permission to retry blindly.

## Owner login fails after downgrade

Try the existing Camera Account for the normal post-boot local reads described in the guide. The previous owner login failed in one verification attempt while the Camera Account subsequently confirmed the expected 1.1.15 build on the same unit. A login failure alone did not establish a failed flash and was not a reason to reset the camera.

Keep the owner/admin, Camera Account and Linux root credentials distinct. Do not put any custom password or raw device report into an issue.

## Telnet does not return after reboot

If you still have another root connection, inspect the saved bootstrap and listener:

```sh
ls -ld /etc/config/local_access
ls -l /etc/config/local_access
cat /tmp/tapo-local-access/bootstrap.log
netstat -lntp
ifconfig br-wan
uci -q get firewall.local_telnet.end_ip
```

Check the following:

- The launcher and worker survived in `/etc/config/local_access/` and match your adapted host files.
- The reserved address matches **every** address occurrence in `camera/boot.sh`, and `br-wan` is the correct interface.
- No `disabled` marker is present and port 2323 is not already occupied.
- The literal startup hook is saved, with its command substitution intact.
- The stock account is enabled and the password is the one that survives boot.

The first experimental bootstrap assumed shadow-only root storage and failed after boot. The corrected script accepts either a direct hash in `/etc/passwd` or a shadow-backed account without writing either file. It rejects empty and locked hashes.

A password change made only in RAM by an initial-access method need not survive reboot. The publicly documented stock default is a separate reference, not a saved custom password. See [the account-layout correction](../reference/how-it-works.md#the-account-layout-bug-and-correction).

If Linux/network access is gone, another network shell is not a recovery plan. The project does not provide a tested physical recovery procedure. Repeated configuration writes or reboots cannot be assumed to fix that state.

## RTSP OPTIONS works, but video stalls

Check **actual video** from both `/stream1` and `/stream2`. The diagnosed failure passed OPTIONS 200 and the Digest challenge, then stalled on authenticated DESCRIBE.

From the existing root shell:

```sh
iptables -S OUTPUT
iptables -S TAPO_LOCAL_ONLY
iptables -nvxL TAPO_LOCAL_ONLY
```

The attached policy must preserve the exact local-address probe:

```text
-d 228.67.43.91 -p udp --sport 15947 --dport 15947 -j RETURN
```

The full rule belongs before the DNS/WAN drops, as in the public bootstrap. Its addition restored DESCRIBE/SETUP/PLAY/RTP immediately in the experiment; the probe counter recorded one 39-byte packet. Correcting the clock, restarting media services or toggling the media-encryption setting did not independently solve that stall. Keep encryption on.

Do not restart the whole stock firewall as a harmless test: it can clear custom isolation. Compare the current rules with the [policy explanation](../reference/how-it-works.md#final-ipv4-egress-policy) and the [persistence procedure](permanent-telnet.md) first.

## ONVIF is not discovered

Try adding the camera by its LAN address and **TCP 2020**, using the Camera Account. The advertised endpoint is `/onvif/service`; the resulting stream URIs use RTSP 554.

The policy includes destination 239.255.255.250, UDP 3702 for discovery, and a LAN return for normal client sessions. Confirm both TCP 2020 and UDP 3702 are listening. A client on another routed subnet may not receive multicast discovery; the experiment verified a direct unicast ProbeMatch, not multicast discovery across the subnet router.

## The clock remains wrong

From an existing root connection:

```sh
date -u
test -e /tmp/time_sync
cat /tmp/tapo-local-access/ntp.log
iptables -nvxL TAPO_LOCAL_ONLY
```

The public bootstrap permits Cloudflare 162.159.200.1 UDP 123 and starts one literal-peer client when the normal sync marker is absent. The vendor peer list can inherit default DNS names even after an override; DNS for those names remains blocked. The literal-peer client bypasses that initial lookup delay, then exits after a real synchronization. Leave the normal stock time service in place.

A corrected clock did not independently fix the RTSP discovery problem. Avoid changing unrelated settings to diagnose it.

## Website or CI checks fail

- **Missing website dependencies:** run `uv run --locked python scripts/site.py prepare` before build/serve. On non-Linux hosts, install Hugo first.
- **Tracked file outside the allowlist:** remove private/generated files from tracking. Add only reviewed project source to `PUBLIC_FILES.txt`.
- **Unlisted website input:** review the file under `docs/content`, `layouts`, `assets` or `static`; do not bypass the check to publish a raw report.
- **Pages not configured:** enable GitHub Actions as the Pages source, then rerun CI and Pages on `main`.
- **Wrong deployment subpath:** use the Pages base URL with its trailing slash. The workflow obtains it from GitHub automatically.

## Report a reproducible issue

Use the [issue tracker](https://github.com/arunoruto/c200-local/issues). Include the hardware revision, source/target firmware build, failing stage, relevant status codes and whether the problem occurred before or after reboot. Describe what remains reachable.

Do not attach passwords, account hashes, Wi-Fi configuration, device identifiers, raw API reports or partition dumps. Shared firmware hashes, model/OEM compatibility values and the documented stock default are public references. [The privacy review](../reference/privacy.md) explains the distinction.
