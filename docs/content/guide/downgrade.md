+++
title = "Downgrade to 1.1.15"
description = "The exact stock image, normal authenticated upload, and post-boot checks."
weight = 10
+++

This is the procedure used on one **C200 hardware 2.0**, from **1.3.17 Build 260112 Rel.58281n(4555)** to **1.1.15 Build 211112 Rel.10589n(4555)**. It uses the normal authenticated firmware-upload endpoint. It does not need an SD card or an existing Linux shell.

{{< callout type="warning" >}}
The upload is a real firmware write. Use stable power and a recovery plan appropriate to your device. Other hardware revisions, OEM variants and source builds have not been tested. Read the steps before starting; an accepted upload starts flashing automatically.
{{< /callout >}}

## 1. Prepare the host and exact stock image

Complete [prerequisites and setup](getting-started.md) first. Run these host commands from the cloned repository root:

```sh
uv sync --locked --group analysis
uv run --locked python scripts/fetch_assets.py --asset c200v2-1.1.15.bin
uv run --locked python scripts/fetch_assets.py --verify-only --asset c200v2-1.1.15.bin
```

These commands download only the downgrade image. You do not need the other firmware or GPL archives for this procedure. The image is:

```text
work/downloads/c200v2-1.1.15.bin
Original filename: Tapo_C200v2_en_1.1.15_Build_211112_Rel.10589n__1637888842077.bin
Size: 8258048 bytes
SHA-256: 12f60580ed051950d22559478dda9453c4312f5a981f4e38212eefbd377eb83e
```

The uploader also checks this size and SHA-256. Use the unmodified image from this exact release. The downloader fetches it from the public reference URL; the repository does not include firmware.

## 2. Record the camera's current state

Replace the example address throughout. Use the normal **owner/admin** login for this operation; a third-party Camera Account that works for RTSP does not necessarily have firmware-update privileges.

```sh
uv run --locked python scripts/read_camera_info.py --host 192.168.1.100 --username admin --firmware work/downloads/c200v2-1.1.15.bin --output private/before-downgrade.json
```

Enter the password at the prompt and keep the report private. Confirm C200 hardware 2.0, the exact source build above, and `exposed_fields_match` for all five compatibility fields. In the Tapo app, turn automatic firmware upgrades off if they are enabled. The uploader requires an idle update state and automatic upgrades to be off. It leaves those settings unchanged.

Have a working third-party **Camera Account** ready for post-downgrade verification before uploading. That login is separate from the owner/admin credentials used for the firmware operation.

All compatibility fields must match before you continue, but a match cannot guarantee a successful flash or boot. The original investigation also checked signatures and package layout offline. The metadata inspector does not check signatures.

## 3. Check the image and upload request offline

```sh
uv run --locked python scripts/downgrade.py --firmware work/downloads/c200v2-1.1.15.bin
```

Without `--attempt`, this command opens no camera connection. It verifies the pinned image, standard single-file multipart body, exact payload bytes, body length and closing MIME footer.

## 4. Submit one upload

The next command sends the firmware and can start flashing:

```sh
uv run --locked python scripts/downgrade.py --host 192.168.1.100 --username admin --baseline private/before-downgrade.json --firmware work/downloads/c200v2-1.1.15.bin --attempt
```

The uploader is based on the client used for the successful downgrade, with private paths and the fixed camera address removed. It prompts for your password, then checks the device identity against your baseline, source build, compatibility fields, update state and automatic-upgrade setting immediately before sending. This version has been tested on a computer, but has not been used for another camera downgrade.

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

A disconnect is ambiguous. **Do not immediately rerun the upload.** Wait for the updater, check reachability and use normal read-only version/status queries before deciding what happened. HTTP acceptance is also not proof of a completed downgrade. The uploader leaves `downgrade_confirmed:false` in its journal. Confirm the running firmware separately after boot; the uploader does not update that field for you.

## 5. Wait and verify the running firmware

Wait for the full interval returned by the camera; the tested response requested 125 seconds. Management and RTSP can disappear while the updater stops services and reboots. Do not interrupt power or initiate another update during that interval.

After services return, use an existing **Camera Account** for normal local reads. In this experiment the previous owner-login verification failed after downgrade, while the existing Camera Account succeeded. A failed owner login alone was not a reason to reset or flash again.

```sh
uv run --locked python scripts/read_camera_info.py --host 192.168.1.100 --username camera-user --firmware work/downloads/c200v2-1.1.15.bin --output private/after-downgrade.json
```

Check the private reports for:

- The same device identity as before; do not publish that identifier.
- Running version `1.1.15 Build 211112 Rel.10589n(4555)`.
- Firmware ID matching the stock image: `D225CC731EB3A3F02C0B81092D0AA04D` where the normal response exposes it.
- Normal update state and automatic upgrades still off, using the app or normal API reads.
- Local RTSP reachability and an authenticated stream, rather than only an open TCP port.

The collector refuses to overwrite an existing output report. For a later verification, choose a new filename such as `private/after-downgrade-check2.json`; keep the original baseline. If the uploader exits with an error after sending, the outcome may still be unknown. Check the running firmware before considering another upload.

The compatibility comparison alone cannot confirm the downgrade. In this test, confirmation came from the running version and firmware ID read from the same camera after boot.

## 6. Continue to persistent Telnet

[Get a root shell using the external guides](initial-shell.md), read [Make it local](make-it-local.md) for the cloud-blocking setup, then follow [permanent Telnet with working RTSP and ONVIF](permanent-telnet.md) to install it.

See the [test results](../reference/validation.md) and [technical explanation](../reference/how-it-works.md) for the original downgrade and its limits.
