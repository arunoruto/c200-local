+++
title = "Initial shell access"
description = "External references for obtaining the prerequisite root shell."
weight = 20
+++

An existing authorized Linux root shell is a prerequisite for the [persistent Telnet procedure](permanent-telnet.md). The [stock downgrade procedure](downgrade.md) uses normal owner/admin authentication and does not require that shell.

For the initial shell, use these maintainer-supplied references:

- [hacefresko/CVE-2021-4045 repository](https://github.com/hacefresko/CVE-2021-4045)
- [Author's blog post](https://www.hacefresko.com/posts/tp-link-tapo-c200-unauthenticated-rce)

This project's procedure begins after root access has been obtained. Continue with [permanent Telnet while preserving RTSP and ONVIF](permanent-telnet.md).
