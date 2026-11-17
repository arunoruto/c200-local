#!/bin/sh
# Restore authenticated local access and the previously tested egress filter.
set -e
umask 077
base=/etc/config/local_access
run=/tmp/tapo-local-access
[ -d "$base" ] && [ ! -L "$base" ] && [ -d "$run" ] || exit 1
[ ! -e "$base/disabled" ] || exit 0
mkdir "$run/lock" 2>/dev/null || exit 0
trap 'rmdir "$run/lock" 2>/dev/null || true' 0
chmod 700 "$base" "$run"
# Accept both stock direct-hash and shadow-backed root layouts.
# Leave all account/password files unchanged; never allow an empty hash.
awk -F: '$1=="root" {n++; if ($3!=0 || ($2!="x" && $2!~/^\$[156]\$/)) bad=1} END {exit (bad || n!=1)}' /etc/passwd
if awk -F: '$1=="root" {exit ($2!="x")}' /etc/passwd; then
    [ -f /etc/shadow ] || exit 1
    awk -F: '$1=="root" {n++; if ($2!~/^\$[156]\$/) bad=1} END {exit (bad || n!=1)}' /etc/shadow
fi
# Restore the exact tested IPv4 policy, building it before attaching it.
if ! iptables -S OUTPUT | awk '$1=="-A" && $2=="OUTPUT" && $3=="-j" && $4=="TAPO_LOCAL_ONLY" && NF==4 {found=1} END {exit !found}'; then
    # Refuse an unexpected unattached chain rather than silently repurposing it.
    if iptables -S TAPO_LOCAL_ONLY >/dev/null 2>&1; then exit 1; fi
    iptables -N TAPO_LOCAL_ONLY
    ok=0
    trap '[ "$ok" = 1 ] || { iptables -F TAPO_LOCAL_ONLY; iptables -X TAPO_LOCAL_ONLY; }; rmdir "$run/lock" 2>/dev/null || true' 0
    iptables -A TAPO_LOCAL_ONLY -o lo -j RETURN
    # Live555 discovers its own LAN IP with this TTL-zero multicast probe.
    iptables -A TAPO_LOCAL_ONLY -d 228.67.43.91 -p udp --sport 15947 --dport 15947 -j RETURN
    # Explicitly owner-approved time service; no general DNS/WAN exception.
    iptables -A TAPO_LOCAL_ONLY -d 162.159.200.1 -p udp --dport 123 -j RETURN
    iptables -A TAPO_LOCAL_ONLY -p udp --dport 53 -j DROP
    iptables -A TAPO_LOCAL_ONLY -p tcp --dport 53 -j DROP
    iptables -A TAPO_LOCAL_ONLY -d 192.168.1.0/24 -j RETURN
    iptables -A TAPO_LOCAL_ONLY -p udp -d 239.255.255.250 --dport 3702 -j RETURN
    iptables -A TAPO_LOCAL_ONLY -p udp -d 255.255.255.255 --sport 68 --dport 67 -j RETURN
    iptables -A TAPO_LOCAL_ONLY -j DROP
    iptables -I OUTPUT 1 -j TAPO_LOCAL_ONLY
    ok=1
fi
# A literal peer avoids vendor default-list DNS lookups delaying first sync.
# One foreground-mode client is detached once per boot and quits on success.
if [ ! -e /tmp/time_sync ] && [ ! -e "$run/ntp-once.pid" ] && [ -x /usr/sbin/ntpd ]; then
    /usr/sbin/ntpd -n -q -p 162.159.200.1 </dev/null >"$run/ntp.log" 2>&1 &
    echo "$!" > "$run/ntp-once.pid"
fi
# Never kill or take over another listener. Repeated starts are harmless.
if [ -s "$run/telnet.pid" ]; then
    read pid < "$run/telnet.pid"
    case "$pid" in ''|*[!0-9]*) exit 1;; esac
    if [ -r "/proc/$pid/cmdline" ] && tr '\000' ' ' < "/proc/$pid/cmdline" | grep -q 'telnetd -F -b 192.168.1.100 -p 2323 -l /bin/login'; then
        echo 'Existing authenticated listener retained.'
        exit 0
    fi
fi
netstat -lnt | awk '$4 ~ /:2323$/ {busy=1} END {exit busy}' || exit 1
[ -x /bin/login ] && [ -x /usr/sbin/telnetd ] || exit 1
# DHCP may still be completing when S45 runs. Keep the wait outside the firewall.
i=0
until ifconfig br-wan | grep -q 'inet addr:192.168.1.100 '; do
    i=$((i+1))
    [ "$i" -lt 90 ] || exit 1
    sleep 1
done
/usr/sbin/telnetd -F -b 192.168.1.100 -p 2323 -l /bin/login > "$run/telnet.log" 2>&1 &
pid=$!
echo "$pid" > "$run/telnet.pid"
sleep 1
kill -0 "$pid"
echo 'Authenticated Telnet ready on LAN port 2323.'
