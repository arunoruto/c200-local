+++
title = "Initial shell access"
description = "Prepare your computer for the camera's reverse connection, then get a root shell."
weight = 20
+++

The [downgrade](downgrade.md) uses your normal owner/admin credentials. To set up permanent Telnet afterward, you'll need a root shell on the camera.

For instructions on getting a shell, see hacefresko's research:

- [hacefresko/CVE-2021-4045 repository](https://github.com/hacefresko/CVE-2021-4045)
- [Author's blog post](https://www.hacefresko.com/posts/tp-link-tapo-c200-unauthenticated-rce)

## Prepare the listener and firewall

With a reverse shell, **the camera connects to a listener on your computer**. If you use TCP **1337**, that port must accept incoming connections on your computer. Replace 1337 throughout if your chosen method uses another port. This is separate from the permanent Telnet listener on the camera's port 2323.

Opening the firewall does not start a listener. Follow the external guide to start it, choose your computer's address that the camera can reach, and make sure the listener binds to that interface or all interfaces rather than only loopback (`127.0.0.1`).

Run the firewall commands below on the **computer hosting the listener**, not on the camera. Choose the section for the firewall you already use; do not run all of them or disable your firewall.

The examples use `192.168.1.100` for the camera. Replace it with the source address your computer actually sees. If a router performs source NAT, that may be the router's address. Remove only rules you added for this task, and close the temporary opening once you no longer need it.

### NixOS

For the standard NixOS iptables/nftables firewall, open the port temporarily:

```sh
sudo nixos-firewall-tool open tcp 1337
```

This is the command used during this project. It opens the port without restricting it to the camera's address, so keep the listener on a trusted network. If NixOS uses firewalld instead, use the firewalld section below. See the [NixOS firewall documentation](https://wiki.nixos.org/wiki/Firewall#Temporary_firewall_rules).

Afterward, restore the configured firewall:

```sh
sudo nixos-firewall-tool reset
```

**Reset removes all temporary openings made with this tool, not just 1337.** Check that you no longer need any of them before resetting. The tool's [source documents the reset behavior](https://github.com/NixOS/nixpkgs/blob/7eee17a8a5868ecf596bbb8c8beb527253ea8f4d/pkgs/by-name/ni/nixos-firewall-tool/nixos-firewall-tool.sh).

### Ubuntu, Debian or Mint with UFW

Use this section if UFW is installed and active. Check its status, then allow only the camera's source address:

```sh
sudo ufw status
sudo ufw allow proto tcp from 192.168.1.100 to any port 1337
```

The rule remains until you remove it; it does not expire when the listener exits. Afterward:

```sh
sudo ufw delete allow proto tcp from 192.168.1.100 to any port 1337
```

If UFW is inactive, adding a UFW rule will not fix a block imposed by another firewall. Use the firewall already managing the host. These commands follow [Ubuntu's UFW documentation](https://ubuntu.com/server/docs/firewalls/).

### Fedora, RHEL or openSUSE with firewalld

Check the active zones:

```sh
sudo firewall-cmd --get-active-zones
```

Use the zone that handles traffic from the camera. Replace `home` below with that zone, and replace the example source address. This runtime rule expires after ten minutes:

```sh
sudo firewall-cmd --zone=home \
  --add-rich-rule='rule family="ipv4" source address="192.168.1.100" port port="1337" protocol="tcp" accept' \
  --timeout=10m
```

To remove it sooner, use the same zone and rule:

```sh
sudo firewall-cmd --zone=home \
  --remove-rich-rule='rule family="ipv4" source address="192.168.1.100" port port="1337" protocol="tcp" accept'
```

Leave out `--permanent`; no reload is needed for this runtime change. The [firewall-cmd manual](https://firewalld.org/documentation/man-pages/firewall-cmd.html) covers zones, timeouts and removal, and the [rich-rule manual](https://firewalld.org/documentation/man-pages/firewalld.richlanguage.html) documents source and port matching.

### Windows

Open **PowerShell as Administrator** on the listener computer. Check the network profile, then add a rule limited to the camera's source address:

```powershell
Get-NetConnectionProfile
New-NetFirewallRule -Name "C200-InitialShell" -DisplayName "C200 initial shell" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1337 -RemoteAddress 192.168.1.100 -Profile Private
```

The example applies to a **Private** network. If the listener's interface uses another profile, choose the matching firewall profile (`Public` or `Domain`) in the rule. There is no need to change the whole network's category.

This rule persists until removed. Afterward:

```powershell
Remove-NetFirewallRule -Name "C200-InitialShell"
```

Microsoft documents [network-profile checks](https://learn.microsoft.com/en-us/powershell/module/netconnection/get-netconnectionprofile), [creating a rule](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule), and [removing it by name](https://learn.microsoft.com/en-us/powershell/module/netsecurity/remove-netfirewallrule).

### macOS

The built-in macOS firewall allows incoming connections by app or service rather than through a simple port-opening command. In **System Settings → Network → Firewall → Options**, add the program that owns the listener and choose **Allow incoming connections**. Check that **Block all incoming connections** is not overriding it.

Afterward, restore the program's previous setting or remove the exception you added. Apple's [firewall settings guide](https://support.apple.com/guide/mac-help/mh11783/mac) explains the app list and controls. A separate packet filter or third-party firewall may also need an exception.

## If the camera still cannot connect

Check the whole camera-to-computer path:

- The listener is running on the configured TCP port and a reachable address, not only loopback.
- The host rule matches the incoming interface, zone or Windows profile, and the source address seen by the host.
- Router, VLAN, Wi-Fi client-isolation and VPN rules allow the camera to reach your computer. Being able to connect from your computer to the camera does not prove the reverse direction works.
- If the listener runs in a VM, container or WSL, its port must also be reachable through the host and guest networking setup.

For remote access through a subnet router, use a listener on the camera's LAN or verify a route back to the remote computer. Opening the host firewall alone does not create that route. See [the address and routing notes](getting-started.md#use-the-right-machine-and-address).

## Continue to permanent Telnet

Once you have a root shell, follow the [permanent Telnet guide](permanent-telnet.md) to keep shell access after reboot without losing RTSP or ONVIF. The reverse-listener port is for initial access; it does not need to remain open after you have verified the permanent connection.
