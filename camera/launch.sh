#!/bin/sh
# Called by the normal firewall generator; never print to its command output.
umask 077
base=/etc/config/local_access
[ ! -e "$base/disabled" ] || exit 0
run=/tmp/tapo-local-access
[ ! -L "$run" ] || exit 1
mkdir -p "$run" || exit 1
chmod 700 "$run" || exit 1
/bin/sh "$base/boot.sh" </dev/null >"$run/bootstrap.log" 2>&1 &
exit 0
