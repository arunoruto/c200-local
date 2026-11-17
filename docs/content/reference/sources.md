+++
title = "Sources & acknowledgments"
description = "Primary sources, prior camera research and third-party credits."
weight = 30
+++

These sources informed the investigation. The [technical explanation](how-it-works.md) and [test results](validation.md) describe what was observed on this camera and what came from earlier research. Firmware and third-party code stay at their linked sources. Camera observations were recorded on 2026-11-16/17.

## Vendor material

- [TP-Link C200 V2 support](https://www.tp-link.com/en/support/download/tapo-c200/v2/): model-specific downloads and GPL link.
- [EU firmware release notes](https://www.tp-link.com/fr/support/download/tapo-c200/v2/#Firmware-Release-Notes).
- [Historical official camera GPL archive](https://static.tp-link.com/resources/gpl/camera_slp_realtek_c200.tar.bz2): historical platform/toolchain/init sources; not a complete current camera SDK.
- [Stock 1.3.17 image used for analysis](https://download.tplinkcloud.com/firmware/Tapo_C200v2_en_1.3.17_Build_260112_Rel.58281n_up_boot-signed_1770802078576.bin): original TP-Link CDN object, hash pinned in the manifest.
- [TP-Link RTSP/ONVIF guide](https://www.tp-link.com/us/support/faq/2680/): Camera Account setup, RTSP 554 and ONVIF 2020.
- [TP-Link2025 advisory](https://www.tp-link.com/us/support/faq/4849/) and [2026 diagnostic advisory](https://www.tp-link.com/uk/support/faq/5321/): check the listed hardware revisions and builds before applying either advisory to a V2 camera.

## RTSP and time

- [Released Live555 GroupsockHelper.cpp](https://nest-open-source.googlesource.com/nest-cam/4320010/live555/+/c98cf70995ccdb2054765a8a14f8a0d12f245681/live555/groupsock/GroupsockHelper.cpp): `ourIPAddress()`, TTL-zero multicast probe 228.67.43.91/15947 and hostname fallback. Allowing that exact probe fixed the camera's observed stall.
- [Cloudflare NTP usage](https://developers.cloudflare.com/time-services/ntp/usage/): literal public time-service addresses.
- [FFprobe documentation](https://ffmpeg.org/ffprobe.html): independent decoding and documented argument-file input syntax used to avoid credentials in process arguments.

## Existing C200 research

- [nervous-inhuman/tplink-tapo-c200-re](https://github.com/nervous-inhuman/tplink-tapo-c200-re) and [shell-access discussion](https://github.com/nervous-inhuman/tplink-tapo-c200-re/discussions/6).
- [Historical CVE-2021-4045 research](https://www.hacefresko.com/posts/tp-link-tapo-c200-unauthenticated-rce): earlier work on initial access, which was not reproduced as part of this project.
- [DrmnSamoLiu's Telnet/persistence article](https://drmnsamoliu.github.io/telnet.html): prompted the ART comparison; this project's installed solution does not flash ART.
- [Downgrading Tapo Cams](https://github.com/DrmnSamoLiu/Downgrading-Tapo-Cams) and [V2 downgrade reports](https://github.com/nervous-inhuman/tplink-tapo-c200-re/issues/4#issuecomment-2167753811).
- [Stock C200 firmware archive](https://github.com/tapo-firmware/Tapo_C200/tree/main/Tapo_C200v2): historical reference images, including the 1.1.15 package used.
- [Firmware catalog](https://tpbreak.afflicted.sh/api/files?model=Tapo%20C200) and [firmware index](https://github.com/Ripthulhu/tp-link-tapo-firmware/blob/main/tapo_firmware.csv): discovery aids; local SHA-256 checks establish exact inputs.
- [OPSWAT camera-chain research](https://www.opswat.com/blog/from-authentication-bypass-to-full-camera-compromise): background on diagnostic paths that depend on the firmware version; those exploits were not applied here.
- [C210 image-format research](https://watchfulip.github.io/28-12-24/tp-link_c210_v2.html) and [robbins/tp-link-decrypt](https://github.com/robbins/tp-link-decrypt): references for other package formats; the examined C200 SquashFS contents were readable directly.

## Tools and platform references

- [PyTapo](https://github.com/JurajNyiri/pytapo), including its documented authentication and TLS transport behavior. The project pins 3.4.31.
- [Dissect SquashFS](https://github.com/fox-it/dissect.squashfs): bounded offline filesystem inspection/extraction; pinned with its supporting packages.
- [uv](https://docs.astral.sh/uv/): environment and dependency management.
- [Requests timeouts](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts): a client timeout is not a rollback or proof that an operation never executed.
- [OpenIPC TP-Link hardware inventory](https://github.com/OpenIPC/wiki/blob/master/en/tp-link.md) and [Realtek platform discussion](https://github.com/OpenIPC/firmware/issues/1092).
- [Realtek toolchain reference](https://github.com/code-explorer1234/RTS3903N-rsdk-4.8.5-5281) and [Yi RTS3903N RTSP project](https://github.com/code-explorer1234/Yi-RTS3903N-RTSPServer): projects for the same chip that may help further research, but are not ready-to-flash Tapo firmware.
- [Thingino C200 profile](https://thingino.com/cameras/46): documents a different platform configuration; its model name alone is insufficient for compatibility.

Thanks to the authors of these tools, released sources, firmware archives and earlier investigations. This project adds traces and tests from the camera, checks of configuration persistence, the account-layout correction, the diagnosis of RTSP stalling after an isolated boot, and the accompanying tools and documentation.

## Documentation website

- [Hugo](https://gohugo.io/): the static generator; the tested binary is 0.170.0.
- [Hextra](https://github.com/imfing/hextra) and [its documentation](https://imfing.github.io/hextra/docs/): the 0.13.0 theme, navigation, syntax highlighting and search interface.
- [FlexSearch](https://github.com/nextapps-de/flexsearch): the 0.8.143 search runtime, served locally from the generated site.

Dependency versions, download URLs and SHA-256 digests are pinned in `docs/dependencies.json`. The generated site preserves the Hextra and FlexSearch license notices.
