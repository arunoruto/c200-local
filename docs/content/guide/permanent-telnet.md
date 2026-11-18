+++
title = "Permanent Telnet"
description = "Save authenticated Telnet without losing RTSP or ONVIF."
weight = 40
+++

Start after the [stock downgrade](downgrade.md), with a [root shell open on the camera](initial-shell.md). These steps save the Telnet startup scripts in user configuration, using the method tested on **C200 V2 stock 1.1.15**. They keep your existing Linux password and `/bin/login`, and allow the local streaming and discovery traffic needed while the cloud is blocked. Read [Make it local](make-it-local.md) first for the firewall policy and its limits; this procedure installs and saves that policy together with Telnet.

The `camera/` files match the tested startup scripts, with an example address in place of the camera's address. These instructions are for matching firmware. The published steps have not been repeated as a fresh camera installation. If you already have `TAPO_LOCAL_ONLY` installed or use different firmware, review your current setup before continuing.

Commands labeled **host** run on your computer. Commands labeled **camera** run inside the existing root shell. Saving configuration writes flash. If interrupted, it can leave the camera unreachable over Wi-Fi. Backups were taken during testing, but physical recovery has not been tested.

Know the Linux password that the stock camera will use after reboot. The startup scripts use normal login authentication. A password change made only in RAM while getting the initial shell will not be saved by these scripts. The tested setup used the stock account files and password. Both direct-hash and shadow-backed accounts are supported without changing either password file.

The shared stock root password is `slprealtek`, as [documented in the original C200 research](https://github.com/nervous-inhuman/tplink-tapo-c200-re#default-root-password-and-u-boot-console). Use your actual Linux password if it differs; the Camera Account is separate.

## 1. Record the baseline and back up off-device

On the **camera**:

```sh
id
cat /proc/mtd
cat /proc/mounts
netstat -lntup
uci changes
iptables -S OUTPUT
```

Confirm the camera reports stock 1.1.15, your shell has root access, and the Camera Account works. Use the [service checklist](verify-streams.md) to check both RTSP streams and ONVIF before changing anything. Open your player and client windows, and have all three logins ready before starting the timed trial.

Review any pending UCI changes; do not discard them with a blanket revert. If `system` or `firewall` already has pending changes, review them before continuing: the later commits will save those changes too. Stop if port 2323 is already occupied or a custom OUTPUT chain is attached.

Create private baseline files on the **camera**:

```sh
umask 077
mkdir -p /tmp/local-access-backup
cat /proc/mtd > /tmp/local-access-backup/mtd.txt
md5sum /dev/mtdblock0 /dev/mtdblock1 /dev/mtdblock2 /dev/mtdblock3 /dev/mtdblock4 /dev/mtdblock5 /dev/mtdblock6 /dev/mtdblock7 /dev/mtdblock8 > /tmp/local-access-backup/flash-before.md5
md5sum /etc/passwd /etc/shadow > /tmp/local-access-backup/accounts-before.md5
iptables-save > /tmp/local-access-backup/iptables-before.rules
tar -czf /tmp/local-access-backup/user-config-before.tar.gz -C /tmp/etc uc_conf
dd if=/dev/mtdblock3 of=/tmp/local-access-backup/config-before.bin bs=65536 count=1
```

These partition numbers refer to the exact tested layout: mtd3 is the 65,536-byte user-config view. Compare your `/proc/mtd` first. Do not guess offsets or concatenate these partition views into a full flash image.

**Transfer the backup directory to private storage on the host using your existing root/file-transfer connection before continuing.** `/tmp` is lost at reboot. The configuration archive and partition contain private device data; never attach them to GitHub issues. The original test also saved and independently checked readbacks of all nine partitions.

## 2. Set the camera address in the startup script

On the **host**, edit `camera/boot.sh` **inside the cloned repository**; that is the file served in step 3. The [downloadable copy](/downloads/boot.sh) is the unadapted template. Leave `camera/launch.sh` unchanged.

- Replace every `192.168.1.100` with the fixed address reserved for your camera.
- Replace `192.168.1.0/24` with your actual LAN subnet if it differs. Your management and streaming clients must be reachable through that permitted subnet; see the [routed/VPN access requirement](getting-started.md#use-the-right-machine-and-address).
- Check that `br-wan` is the interface carrying that address on your matching firmware.

Keep the Live555, ONVIF and DHCP exceptions. Do not change `/bin/login`, remove the account guard, insert a root hash, or disable media encryption. The tested stock boot stores root's hash directly in `/etc/passwd`; the script also supports an enabled shadow-backed account. It rejects empty/locked account hashes and writes neither password file.

The launcher [camera/launch.sh](/downloads/launch.sh) starts the worker in the background and redirects its input and output so it does not block firewall startup. The worker builds the IPv4 filter, waits up to 90 seconds for the fixed address, then starts one password-authenticated Telnet listener on 2323. Installing it requires root access.

## 3. Copy the scripts to the camera (RAM only)

The HTTP transfer example assumes the camera can reach the host at its example LAN address before isolation is applied. If you work only through a remote subnet router, use the file-transfer method available through your existing root connection instead. Copying the files alone does not save them for the next boot.

For example, serve only the public script directory from the **host**:

```sh
uv run --locked python -m http.server 8000 --bind 192.168.1.10 --directory camera
```

Use your host's LAN address instead of `192.168.1.10`. From the **camera**:

```sh
umask 077
mkdir -p /etc/config/local_access
chmod 700 /etc/config/local_access
wget -O /etc/config/local_access/launch.sh http://192.168.1.10:8000/launch.sh
wget -O /etc/config/local_access/boot.sh http://192.168.1.10:8000/boot.sh
chmod 600 /etc/config/local_access/launch.sh /etc/config/local_access/boot.sh
sh -n /etc/config/local_access/launch.sh
sh -n /etc/config/local_access/boot.sh
md5sum /etc/config/local_access/launch.sh /etc/config/local_access/boot.sh
```

Compare those hashes with the adapted files on the host. Stop the host HTTP server after the transfer. These files are currently in the RAM-backed configuration tree; do not commit yet.

## 4. Test the listener and filter before saving

Keep the original root connection open throughout the trial. Prepare the checks below first: the three-minute deadline begins when the background rollback starts, not when you log into port 2323. On the **camera**, arm a three-minute filter/listener rollback:

```sh
rm -f /tmp/local-access-keep
cat > /tmp/local-access-rollback.sh <<'ROLLBACK'
sleep 180
[ ! -e /tmp/local-access-keep ] || exit 0
iptables-restore < /tmp/local-access-backup/iptables-before.rules
if [ -s /tmp/tapo-local-access/telnet.pid ]; then
    read pid < /tmp/tapo-local-access/telnet.pid
    case "$pid" in ''|*[!0-9]*) exit 1;; esac
    if [ -r "/proc/$pid/cmdline" ] && tr '\000' ' ' < "/proc/$pid/cmdline" | grep -q 'telnetd -F -b .* -p 2323 -l /bin/login'; then
        kill "$pid"
    fi
fi
ROLLBACK
sh /tmp/local-access-rollback.sh </dev/null >/tmp/local-access-rollback.log 2>&1 &
sh /etc/config/local_access/launch.sh
```

The background process restores the previous rules and stops the new 2323 listener unless you create the keep marker. It cannot undo flash writes or recover a camera that fails to boot. Do not commit or save configuration during this trial.

Within that interval, open a **new host connection**:

```sh
telnet 192.168.1.100 2323
```

Log in as root with the existing Linux password, run `id`, and check that an empty password is refused in a separate connection. Do not confuse the Linux root password with the Camera Account used below.

Then verify all of these while the filter is attached:

| Check | Expected |
|---|---|
| RTSP main with Camera Account | `rtsp://192.168.1.100:554/stream1`, actual video |
| RTSP secondary with Camera Account | `rtsp://192.168.1.100:554/stream2`, actual video |
| ONVIF client/NVR | Camera address, TCP 2020, existing Camera Account; enumerate both profiles and obtain their stream URIs |
| ONVIF discovery | UDP 3702 is listening; verify discovery from your LAN client if supported |
| Local API | Fresh normal authenticated device-information read |

Enter credentials in the client's login fields. Putting them in a URL can expose them in process arguments. Check actual video: an open port and RTSP OPTIONS 200 both worked during the earlier streaming failure.

On the **camera**, inspect:

```sh
cat /tmp/tapo-local-access/bootstrap.log
iptables -S OUTPUT
iptables -nvxL TAPO_LOCAL_ONLY
md5sum -c /tmp/local-access-backup/accounts-before.md5
uci -q get cet.media_encrypt.enabled
```

Accounts must match, encryption must remain `on`, and the rule set must include:

```text
-d 228.67.43.91 -p udp --sport 15947 --dport 15947 -j RETURN
-d 239.255.255.250 -p udp --dport 3702 -j RETURN
```

The first allows Live555's TTL-zero local-address probe; omitting it caused authenticated DESCRIBE to stall after boot. The second permits ONVIF discovery. The LAN-return rule carries the actual RTSP/API/ONVIF sessions. DNS drops precede LAN return, and Cloudflare 162.159.200.1 UDP/123 is the only external unicast exception.

Only after the checks pass, cancel rollback by creating the marker on the **camera**:

```sh
touch /tmp/local-access-keep
```

If any check fails or you cannot finish before the deadline, leave the marker absent and let rollback run. If the timer already expired, inspect the rollback log and restore a working baseline before trying again. A keep marker created after expiry does not reapply the filter or restart the listener. Do not create the marker merely because the old shell remains connected.

## 5. Configure the saved startup hook

On the **camera**, set the firewall startup hook exactly as shown:

```sh
uci set firewall.ipctrl.enabled=on
uci set firewall.ipctrl.filter_mode=blacklist
uci set firewall.local_telnet=blacklist
uci set firewall.local_telnet.start_ip=203.0.113.254
uci set 'firewall.local_telnet.end_ip=203.0.113.254$(sh${IFS}/etc/config/local_access/launch.sh)'
uci changes firewall
```

Keep the last assignment single-quoted: the substitution must be saved literally for the vendor-generated script, not expanded by the current shell. `203.0.113.254` is a documentation source address, not your camera or loopback. The blacklist range contains only that documentation address. When the vendor-generated script runs, the saved command substitution starts the launcher.

The stock `S45firewall` startup script runs this hook at boot. **Do not restart the complete stock firewall to test it**; that can remove the isolation rules. The hook was first checked with a temporary UCI configuration and simulated iptables commands, without restarting the camera's firewall.

The tested setup also used this IP address for the normal NTP service:

```sh
uci set system.ntp.server=0.0.0.0
uci -q delete system.ntp.def_server || true
uci add_list system.ntp.def_server=162.159.200.1
uci changes system
```

The vendor list may still include default DNS names, whose lookups remain blocked. The startup script also runs a once-per-boot NTP client using the IP address directly, so the first synchronization does not wait for DNS. This keeps time accurate; it did not fix the RTSP stall.

## 6. Commit and save user configuration

The next steps save configuration to flash. Review all pending changes first. On the **camera**, record the adapted scripts before saving:

```sh
md5sum /etc/config/local_access/launch.sh /etc/config/local_access/boot.sh > /tmp/local-access-backup/scripts-before.md5
cat /proc/uptime > /tmp/local-access-backup/uptime-before.txt
uci changes > /tmp/local-access-backup/uci-pending.txt
```

Compare `scripts-before.md5` with the adapted host files and transfer these baseline files off-device too. On this firmware **`uci commit` can invoke the flash saver**; the first commit may already save the whole user-config tree. These are not RAM-only commands.

On the **camera**:

```sh
uci commit system && uci commit firewall && /bin/uc_convert -t 1 && sync
md5sum -c /tmp/local-access-backup/accounts-before.md5
md5sum /dev/mtdblock0 /dev/mtdblock1 /dev/mtdblock2 /dev/mtdblock3 /dev/mtdblock4 /dev/mtdblock5 /dev/mtdblock6 /dev/mtdblock7 /dev/mtdblock8 > /tmp/local-access-backup/flash-after.md5
awk 'NR==FNR {old[$2]=$1; next} old[$2]!=$1 {print "changed:", $2}' /tmp/local-access-backup/flash-before.md5 /tmp/local-access-backup/flash-after.md5
dd if=/dev/mtdblock3 of=/tmp/local-access-backup/config-after.bin bs=65536 count=1
md5sum /dev/mtdblock3 /tmp/local-access-backup/config-after.bin
```

Run the save line first and confirm it succeeds before running the readback/comparison lines. Check each command's exit status; stop on a failure. The `awk` comparison must print only `changed: /dev/mtdblock3`; it does not signal an unexpected change through its exit status. The commits may write flash before the separate saver call, so these commands can cause more than one physical write. The only changed partition must be mtd3 user configuration. Account files must remain identical. The physical readback's checksum must equal the device view. Copy the new checksums and readback off the camera too.

The original test also restored the proposed configuration twice in an isolated environment using ordinary files instead of a flash device. It then restored the physical readback twice to check every expected file. Those test adapters are not included in this guide. A matching readback size and checksum alone cannot show that every file will restore correctly. Do not run `uc_convert -t 0` on the live camera just to check the backup: it restores configuration.

## 7. Reboot once, then check all local services

After the save checks and recovery preparation, issue one normal `reboot` from the existing root connection. Wait for the camera to return; do not repeatedly send reboot or save commands because the network drops.

Verify fresh root/password login on 2323, empty-password refusal, normal local API reads, actual video from **both** RTSP streams and ONVIF capabilities/profiles/stream URIs. Check uptime to confirm the reboot, then check again after at least 180 seconds for the first watchdog scan. The RAM backup directory is gone after reboot. Run these **camera** commands and compare their output with the off-device files you saved:

```sh
cat /proc/uptime
md5sum /etc/config/local_access/launch.sh /etc/config/local_access/boot.sh
md5sum /etc/passwd /etc/shadow
md5sum /dev/mtdblock0 /dev/mtdblock1 /dev/mtdblock2 /dev/mtdblock3 /dev/mtdblock4 /dev/mtdblock5 /dev/mtdblock6 /dev/mtdblock7 /dev/mtdblock8
```

Use `scripts-before.md5` for the adapted scripts, `accounts-before.md5` for accounts, and **`flash-after.md5`** for all nine partitions, including the saved configuration. Compared with `flash-before.md5`, only mtd3 should differ. The uptime should show the new boot. Repeat the [service checklist](verify-streams.md) to confirm streaming and local control as well as Telnet.

Also check:

```sh
iptables -S OUTPUT
iptables -nvxL TAPO_LOCAL_ONLY
date -u
test -e /tmp/time_sync
uci -q get cet.media_encrypt.enabled
```

After reboot, the camera had accurate time, the sync marker, and encryption ON. The stock watchdog and cloud processes kept running behind the filter. Each stream decoded 75 frames over a five-second interval, and a unicast ONVIF probe received a ProbeMatch. The setup works with those stock processes and watchdog unchanged.

## Disable the saved bootstrap if needed

From a working root connection, `touch /etc/config/local_access/disabled` prevents future direct launches. Save configuration with the normal saver if you want the marker to survive reboot. It does not remove a running listener or currently attached chain.

To remove the startup hook, first restore another working access/policy path, then delete only the `firewall.local_telnet` section and save deliberately. Restore the original IP-control and NTP settings from your private baseline where needed, taking care to keep any other firewall policy in place. Removing the hook alone does not restore a blocked network in the current boot. Raw partition restoration and recovery are outside this guide.

See [tested results and limits](../reference/validation.md) before relying on this setup through address changes, full firewall reloads, physical power cycles or long streaming sessions. The filter covers IPv4 only.
