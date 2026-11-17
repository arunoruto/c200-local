+++
title = 'Troubleshooting'
description = 'Identify the failing stage without blindly repeating firmware writes, restarts or configuration saves.'
weight = 50
+++

Start with the step that failed. An open TCP port, an accepted upload or an RTSP OPTIONS response only confirms part of the process. Check the running firmware, login and actual video before calling it successful.

## Firmware upload disconnects or times out

Do not automatically resubmit. The stock handler stops services before receiving the whole image, and the updater can close management connections. The uploader sends once and never retries a firmware POST.

Wait for the full interval returned by the camera. When management returns, collect fresh device information and compare the same-device running version with the private baseline. HTTP200 with `error_code:0` means accepted, not completed. See [the upload and timeout record](downgrade.md#why-the-timeout-matters).

The first test disconnected with a 15-second timeout. A later, separately started request with 120 seconds was accepted. Both socket timeouts in this uploader are 120 seconds. If another request times out, check the camera before considering a retry.

## Owner login fails after downgrade

Try the existing Camera Account for the normal post-boot local reads described in the guide. In one check after the downgrade, the owner login failed but the Camera Account worked and confirmed the expected 1.1.15 build on the same camera. A failed login alone does not mean the flash failed, so check with the other account before considering a reset.

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

A password change made only in RAM by an initial-access method need not survive reboot. The documented stock default and a custom password are different credentials; use the one the camera restores at boot. See [the account-layout correction](../reference/how-it-works.md#the-account-layout-bug-and-correction).

If Linux or networking no longer starts, you cannot recover through another network shell. Physical recovery has not been tested for this project. Repeating configuration writes or reboots may leave the camera just as unreachable.

## RTSP OPTIONS works, but video stalls

Check **actual video** from both `/stream1` and `/stream2`. The diagnosed failure passed OPTIONS 200 and the Digest challenge, then stalled on authenticated DESCRIBE.

From the existing root shell:

```sh
iptables -S OUTPUT
iptables -S TAPO_LOCAL_ONLY
iptables -nvxL TAPO_LOCAL_ONLY
```

The attached filter must allow this exact local-address probe:

```text
-d 228.67.43.91 -p udp --sport 15947 --dport 15947 -j RETURN
```

The full rule belongs before the DNS/WAN drops, as in the startup script. Its addition restored DESCRIBE/SETUP/PLAY/RTP immediately in the experiment; the probe counter recorded one 39-byte packet. Correcting the clock, restarting media services or toggling the media-encryption setting did not independently solve that stall. Keep encryption on.

Restarting the whole stock firewall can remove the isolation rules. Avoid using a firewall restart to diagnose this problem. Compare the current rules with the [policy explanation](../reference/how-it-works.md#final-ipv4-egress-policy) and the [persistence procedure](permanent-telnet.md) first.

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

The startup script allows Cloudflare 162.159.200.1 UDP 123 and starts one NTP client using that IP address when the normal sync marker is absent. The vendor peer list can still include default DNS names after an override, but those lookups remain blocked. Using the IP address avoids that lookup delay; the extra client exits after synchronization. Leave the stock time service in place.

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
