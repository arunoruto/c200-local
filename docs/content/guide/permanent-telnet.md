+++
title = "Permanent Telnet"
description = "Save authenticated Telnet without losing RTSP or ONVIF."
weight = 30
+++

Use this after the [stock downgrade](downgrade.md) and after obtaining an [authorized root shell](initial-shell.md). The following manual procedure publishes the configuration-backed method verified on **C200 V2 stock 1.1.15**. It keeps the existing Linux password and normal `/bin/login`, saves startup through user configuration and preserves the local media/discovery traffic needed when blocking the cloud.

The `camera/` files match the final verified bootstrap except that the device-specific address is replaced with an example. The commands below assemble that setup on a fresh matching system. This public presentation has not been rerun against the already configured camera. Do not apply it over an existing `TAPO_LOCAL_ONLY` installation or a different firmware without reviewing that state.

Commands labeled **host** run on your computer. Commands labeled **camera** run inside the existing root shell. Saving configuration writes flash and can lose Wi-Fi access if interrupted. The experiment has private backups but no demonstrated physical recovery procedure.

Know the Linux password that the stock camera will use after reboot. The bootstrap preserves normal authentication; it does not persist a password change made only in RAM by an initial-access method. The tested final baseline used the stock account files/password, and the bootstrap supports both direct-hash and shadow-backed layouts without writing either file.

The stock default `slprealtek` is a [publicly documented firmware reference](https://github.com/nervous-inhuman/tplink-tapo-c200-re#default-root-password-and-u-boot-console), not a private per-device password. Use your actual Linux password if it differs; the Camera Account is separate. This identifies the normal login credential, not a procedure for obtaining the prerequisite shell.

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

Confirm stock 1.1.15 through normal device information, root access and a working Camera Account. Check both RTSP streams and ONVIF before changing anything. Preserve any pre-existing pending UCI changes; do not discard them with a blanket revert. Stop if port 2323 is already occupied or an existing custom OUTPUT chain is attached.

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

These partition numbers refer to the exact tested layout: mtd3 is the 65,536-byte user-config view. Compare your `/proc/mtd` first. Do not infer offsets or assemble a chip image by concatenating views.

**Transfer the backup directory to private storage on the host using your existing root/file-transfer connection before continuing.** `/tmp` is lost at reboot. The configuration archive and partition contain private device data; never attach them to GitHub issues. The original experiment additionally saved and independently verified all nine partition readbacks.

## 2. Adapt the public bootstrap

On the **host**, edit [camera/boot.sh](/downloads/boot.sh):

- Replace every `192.168.1.100` with the fixed address reserved for your camera.
- If necessary, replace `192.168.1.0/24` with your actual LAN subnet.
- Check that `br-wan` is the interface carrying that address on your matching firmware.

Keep the Live555, ONVIF and DHCP exceptions. Do not change `/bin/login`, remove the account guard, insert a root hash, or disable media encryption. The tested stock boot stores root's hash directly in `/etc/passwd`; the script also supports an enabled shadow-backed account. It rejects empty/locked account hashes and writes neither password file.

The launcher [camera/launch.sh](/downloads/launch.sh) starts the worker asynchronously with redirected descriptors. The worker builds the complete IPv4 filter, waits up to 90 seconds for the fixed address and starts one password-authenticated listener on 2323. It is not a root-acquisition mechanism.

## 3. Copy the scripts into the RAM configuration tree

The HTTP transfer example assumes the camera can reach the host at its example LAN address before isolation is applied. If you work only through a remote subnet router, use the file-transfer method available through your existing root connection instead. Transfer is separate from the saved startup mechanism.

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

Keep the original root connection open. On the **camera**, arm an independent three-minute filter/listener rollback:

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

The independent background process restores the prior rules and stops the new 2323 listener unless the keep marker is created. It does not undo persistent writes and is not a recovery method after a bad reboot. No commit/save belongs in this trial.

Within that interval, open a **new host connection**:

```sh
telnet 192.168.1.100 2323
```

Log in as root with the existing Linux password, run `id`, and explicitly verify that an empty password is refused in a separate connection. Do not confuse the Linux root password with the Camera Account used below.

Then verify all of these while the filter is attached:

| Check | Expected |
|---|---|
| RTSP main with Camera Account | `rtsp://192.168.1.100:554/stream1`, actual video |
| RTSP secondary with Camera Account | `rtsp://192.168.1.100:554/stream2`, actual video |
| ONVIF client/NVR | Camera address, TCP 2020, existing Camera Account; enumerate both profiles and obtain their stream URIs |
| ONVIF discovery | UDP 3702 is listening; verify discovery from your LAN client if supported |
| Local API | Fresh normal authenticated device-information read |

Supply credentials using client login fields, not credential-bearing URLs in process arguments. An open port or RTSP OPTIONS 200 is insufficient: the earlier broken state passed both.

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

If the timer already expired, inspect the rollback log and restore a working baseline before trying again. Do not create the marker merely because the old shell remains connected.

## 5. Configure the saved startup hook

On the **camera**, stage the exact vendor firewall hook:

```sh
uci set firewall.ipctrl.enabled=on
uci set firewall.ipctrl.filter_mode=blacklist
uci set firewall.local_telnet=blacklist
uci set firewall.local_telnet.start_ip=203.0.113.254
uci set 'firewall.local_telnet.end_ip=203.0.113.254$(sh${IFS}/etc/config/local_access/launch.sh)'
uci changes firewall
```

Keep the last assignment single-quoted: the substitution must be saved literally for the vendor-generated script, not expanded by the current shell. `203.0.113.254` is a documentation source address, not your camera or loopback. This creates a harmless actual blacklist range while the generated-script interpretation invokes the launcher.

The stock `S45firewall` path restores the hook at boot. **Do not restart the complete stock firewall to test it**; that can clear retained isolation. The initial interpretation experiment used scratch UCI and stubbed iptables, not a production restart.

For the normal NTP service, the tested setup also staged this literal peer:

```sh
uci set system.ntp.server=0.0.0.0
uci -q delete system.ntp.def_server || true
uci add_list system.ntp.def_server=162.159.200.1
uci changes system
```

The vendor list may still inherit default DNS names. Those lookups remain blocked; the bootstrap's once-per-boot literal-peer client handles the initial real synchronization. This is clock maintenance, not the RTSP fix.

## 6. Commit and save user configuration

This is the persistence/write phase. Review all pending changes and back up the final script checksums before running it. On this firmware **`uci commit` can invoke the flash saver**; the first commit may already save the whole user-config tree. These are not RAM-only commands.

On the **camera**:

```sh
uci commit system && uci commit firewall && /bin/uc_convert -t 1 && sync
md5sum -c /tmp/local-access-backup/accounts-before.md5
md5sum /dev/mtdblock0 /dev/mtdblock1 /dev/mtdblock2 /dev/mtdblock3 /dev/mtdblock4 /dev/mtdblock5 /dev/mtdblock6 /dev/mtdblock7 /dev/mtdblock8 > /tmp/local-access-backup/flash-after.md5
awk 'NR==FNR {old[$2]=$1; next} old[$2]!=$1 {print "changed:", $2}' /tmp/local-access-backup/flash-before.md5 /tmp/local-access-backup/flash-after.md5
dd if=/dev/mtdblock3 of=/tmp/local-access-backup/config-after.bin bs=65536 count=1
md5sum /dev/mtdblock3 /tmp/local-access-backup/config-after.bin
```

Check each command's exit status; stop on a failure. The commits may save before the explicit saver call, so this is not a claim of exactly one physical write. The only changed partition must be mtd3 user configuration. Account files must remain identical. The physical readback's checksum must equal the device view. Transfer the new evidence/readback off-device too.

The original experiment went further: it restored the candidate twice in a device-free file-I/O sandbox and restored the saved physical readback twice to confirm every expected file. Those one-off adapters are not part of this manual guide. Readback size/hash alone does not prove that every file will restore correctly. Do not run `uc_convert -t 0` against the live system as an innocent validation step.

## 7. Reboot once, then repeat the full acceptance checks

After the save checks and recovery preparation, issue one normal `reboot` from the existing root connection. Wait for the camera to return; do not repeatedly send reboot or save commands because the network drops.

Verify fresh root/password login on 2323, empty-password refusal, normal local API reads, actual video from **both** RTSP streams and ONVIF capabilities/profiles/stream URIs. Check uptime to confirm the reboot, then check again after at least 180 seconds for the first watchdog scan. Compare saved script/account hashes and the unchanged firmware/ART/factory partitions against the private baseline.

Also check:

```sh
iptables -S OUTPUT
iptables -nvxL TAPO_LOCAL_ONLY
date -u
test -e /tmp/time_sync
uci -q get cet.media_encrypt.enabled
```

The verified result had accurate time, the sync marker, encryption ON, stock watchdog/cloud processes running behind the filter, 75 decoded frames from each stream over five-second intervals, and a unicast ONVIF ProbeMatch. Neither stopping cloud daemons nor a modified watchdog is required.

## Disable the saved bootstrap if needed

From a working root connection, `touch /etc/config/local_access/disabled` prevents future direct launches. Persist that marker with the normal configuration saver if that is the intended next-boot state. It does not remove a running listener or currently attached chain.

To remove the startup hook, first restore another working access/policy path, then delete only the `firewall.local_telnet` section and save deliberately. Restore the original IP-control/NTP settings from your private baseline as appropriate; do not blindly turn off somebody else's firewall policy. Removing the hook alone does not restore a blocked network in the current boot. Raw partition restoration and recovery are outside this guide.

The fixed listener address, IPv4-only policy, full firewall reloads, physical power cycling and long-duration media behavior retain the limitations in [validation](../reference/validation.md).
