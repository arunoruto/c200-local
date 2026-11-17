+++
title = "Initial shell access"
description = "External references for obtaining the prerequisite root shell."
weight = 20
+++

The [downgrade](downgrade.md) uses your normal owner/admin credentials. To set up permanent Telnet afterward, you'll need a root shell on the camera.

For instructions on getting a shell, see hacefresko's research:

- [hacefresko/CVE-2021-4045 repository](https://github.com/hacefresko/CVE-2021-4045)
- [Author's blog post](https://www.hacefresko.com/posts/tp-link-tapo-c200-unauthenticated-rce)

Once you have a root shell, follow the [permanent Telnet guide](permanent-telnet.md) to keep shell access after reboot without losing RTSP or ONVIF.
