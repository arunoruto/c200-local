+++
title = "The practical guide"
description = "From the stock downgrade to persistent local access."
weight = 10
type = "docs"
[cascade]
type = "docs"
+++

Start with [prerequisites and setup](getting-started.md), then follow the steps in order. The downgrade uses your owner/admin login. To set up permanent Telnet afterward, you need a root shell on the camera.

{{< cards cols="3" >}}
  {{< card link="downgrade" title="1. Downgrade" subtitle="Verify the stock 1.1.15 image, upload once, then check the running version." >}}
  {{< card link="initial-shell" title="2. Initial shell" subtitle="External references for initial access. Persistence begins once you have root." >}}
  {{< card link="permanent-telnet" title="3. Permanent Telnet" subtitle="Back up, test, save the startup hook, then reboot and check every local service." >}}
{{< /cards >}}

## Before starting

- The tested camera is **C200 hardware V2**, originally running **1.3.17 Build 260112 Rel.58281n(4555)**.
- The target is the **unmodified stock 1.1.15** image identified in the downgrade guide.
- Have the normal owner/admin login and a working third-party Camera Account ready. The Linux root password is separate.
- Keep stable power, private off-device backups and a recovery plan. The upload and configuration save both write flash.

This setup worked after a normal reboot on one camera. The uploader and startup scripts in this repository have also been tested on a computer, but the published steps have not been repeated as a fresh camera installation. See [verified results and limits](../reference/validation.md).

## After installation

[Verify both streams, ONVIF and the local API](verify-streams.md). An open port or RTSP OPTIONS response alone does not prove working video. If a check fails, see [troubleshooting](troubleshooting.md).
