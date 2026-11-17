+++
title = "Downgrade to 1.1.15"
description = "The exact stock image, normal authenticated upload, and post-boot checks."
weight = 10
+++

This is the procedure used on one **C200 hardware 2.0**, from **1.3.17 Build 260112 Rel.58281n(4555)** to **1.1.15 Build 211112 Rel.10589n(4555)**. It uses the normal authenticated firmware-upload endpoint. It does not need an SD card or an existing Linux shell.

{{< callout type="warning" >}}
The upload is a real firmware write. Use stable power and a recovery plan appropriate to your device. The successful result on this unit does not establish compatibility with another hardware revision, OEM variant or source build. Read the steps before starting; an accepted upload starts flashing automatically.
{{< /callout >}}

## 1. Prepare the host and exact stock image

Run from the repository root:

```sh
uv sync --locked --group analysis
uv run --locked python scripts/fetch_assets.py --asset c200v2-1.1.15.bin
uv run --locked python scripts/fetch_assets.py --verify-only --asset c200v2-1.1.15.bin
```

This selects only the downgrade image; the other firmware/GPL references are not needed for this procedure. The target is:

```text
work/downloads/c200v2-1.1.15.bin
Original filename: Tapo_C200v2_en_1.1.15_Build_211112_Rel.10589n__1637888842077.bin
Size: 8258048 bytes
SHA-256: 12f60580ed051950d22559478dda9453c4312f5a981f4e38212eefbd377eb83e
```

The uploader independently enforces this size/hash. Do not substitute a modified image or a different release. The package itself is downloaded from the public reference URL, not distributed in this repository.

## 2. Capture a normal owner/admin baseline

Replace the example address throughout. Use the normal **owner/admin** login for this operation; a third-party Camera Account that works for RTSP does not necessarily have firmware-update privileges.

```sh
uv run --locked python scripts/read_camera_info.py --host 192.168.1.100 --username admin --firmware work/downloads/c200v2-1.1.15.bin --output private/before-downgrade.json
```

The password is prompted, not passed in arguments. Keep the report private. Confirm C200 hardware 2.0, the exact source build above, and `exposed_fields_match` for all five compatibility fields. In the Tapo app, turn automatic firmware upgrades off if they are enabled. The uploader checks that the normal update state is idle and automatic upgrades are off; it does not silently change those settings.

Have a working third-party **Camera Account** ready for post-downgrade verification before uploading. That login is separate from the owner/admin credentials used for the firmware operation.

A field match is a necessary precheck in this procedure, not a guarantee of flash/boot success. The original research also checked signatures and package layout offline; the general metadata inspector does not perform those signature checks.

## 3. Check request construction offline

```sh
uv run --locked python scripts/downgrade.py --firmware work/downloads/c200v2-1.1.15.bin
```

Without `--attempt`, this command opens no camera connection. It verifies the pinned image, standard single-file multipart body, exact payload bytes, body length and closing MIME footer.

## 4. Submit one upload

This command is the write boundary:

```sh
uv run --locked python scripts/downgrade.py --host 192.168.1.100 --username admin --baseline private/before-downgrade.json --firmware work/downloads/c200v2-1.1.15.bin --attempt
```

The public uploader is adapted from the successful one-off client. It removes private paths and the fixed device address, prompts for the normal password and checks the same baseline identity, source build, compatibility fields, update state and automatic-upgrade state immediately before sending. The portable adaptation has host-side tests; it has not been used for another live downgrade.

The authenticated request is:

```text
POST https://CAMERA_IP:443/stok=<normal-session>/admin/system/image_upgrade
Content-Type: multipart/form-data; boundary=<generated>
Form field: image
Filename: the original stock 1.1.15 filename
Payload: the complete unmodified stock image
```

The session and TLS compatibility come from the pinned PyTapo transport. Tokens/passwords are never printed or placed in command arguments. Firmware POST redirects and retries are disabled. Both socket timeout values are 120 seconds. The command writes a small mode 0600 journal under `private/`; it does not automatically submit again or request a separate reboot.

### Why the timeout matters

The stock HTTP handler stops services and makes memory available **before** receiving the full body. The first attempt in this project disconnected with a 15-second timeout; the camera later still reported 1.3.17. A separately initiated second attempt using 120 seconds returned HTTP 200, `error_code:0`, `wait_time:125`, then the camera booted 1.1.15.

A disconnect is ambiguous. **Do not immediately rerun the upload.** Wait for the updater, check reachability and use normal read-only version/status queries before deciding what happened. HTTP acceptance is also not proof of a completed downgrade. The uploader deliberately leaves `downgrade_confirmed:false` in its journal until independent post-boot verification is performed.

## 5. Wait and verify the running firmware

Honor the returned wait interval; the tested response requested 125 seconds. Management and RTSP can disappear while the updater stops services and reboots. Do not interrupt power or initiate another update during that interval.

After services return, use an existing **Camera Account** for normal local reads. In this experiment the previous owner-login verification failed after downgrade, while the existing Camera Account succeeded. That was not treated as proof of a failed flash or as a reason to reset/reflash.

```sh
uv run --locked python scripts/read_camera_info.py --host 192.168.1.100 --username camera-user --firmware work/downloads/c200v2-1.1.15.bin --output private/after-downgrade.json
```

Check the private reports for:

- The same device identity as before; do not publish that identifier.
- Running version `1.1.15 Build 211112 Rel.10589n(4555)`.
- Firmware ID matching the stock image: `D225CC731EB3A3F02C0B81092D0AA04D` where the normal response exposes it.
- Normal update state and automatic upgrades still off, using the app or normal API reads.
- Local RTSP reachability and an authenticated stream, rather than only an open TCP port.

The collector reports an exposed-field comparison; that status alone intentionally does not declare a completed downgrade. The same-device running-version/firmware-ID observations supplied the independent confirmation in this project.

## 6. Continue to persistent Telnet

[Obtain an authorized root shell using the maintainer's separate reference](initial-shell.md). That topic is outside this guide. Once you have root on the downgraded camera, follow [persistent Telnet with working RTSP and ONVIF](permanent-telnet.md).

For the original observed sequence and limitations, see [validation](../reference/validation.md) and [research notes](../reference/how-it-works.md).
