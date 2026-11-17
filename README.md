# C200 Local

[Live documentation](https://arunoruto.github.io/c200-local/) · [Repository](https://github.com/arunoruto/c200-local) · [CI and deployment](https://github.com/arunoruto/c200-local/actions/workflows/docs.yml)

Downgrade **Tapo C200 V2** to stock **1.1.15**, make normal Telnet login survive reboot, and preserve **RTSP and ONVIF with the cloud blocked**.

The setup was verified on one V2 camera on 17 November 2026. Original code and documentation are [MIT licensed](LICENSE). Firmware and private device data are not distributed.

## Follow the guide

Start with [prerequisites and setup](docs/content/guide/getting-started.md).

1. [Downgrade from 1.3.17 to 1.1.15](docs/content/guide/downgrade.md).
2. [Initial shell access](docs/content/guide/initial-shell.md) — links to the external repository and author's blog post.
3. [Make Telnet permanent](docs/content/guide/permanent-telnet.md).
4. [Verify both streams, ONVIF and local access](docs/content/guide/verify-streams.md).

For common failures, see [troubleshooting](docs/content/guide/troubleshooting.md).

The full documentation lives in **docs/** as a Hugo site using **Hextra**. [Technical reference](docs/content/reference/how-it-works.md), [verified results and limits](docs/content/reference/validation.md), and [source credits](docs/content/reference/sources.md) distinguish live camera results from tested public adaptations.

## Preview the documentation

```sh
uv sync --locked --group analysis
uv run --locked python scripts/site.py prepare
uv run --locked python scripts/site.py serve
```

Open `http://localhost:1313/` on the same host. To produce static HTML:

```sh
uv run --locked python scripts/site.py build
```

The output is **docs/public/**. Preparation installs pinned Hugo/Hextra/search dependencies locally on supported Linux hosts; other systems need Hugo installed first. No Node or Go toolchain is required. See [build and contribution notes](docs/content/contributing.md) for deployment, GitHub Pages and public-source packaging.

## CI and GitHub Pages

The [CI and Pages workflow](.github/workflows/docs.yml) runs on pull requests and pushes to `main`:

1. Audit tracked source and run the host tests with the pinned offline firmware fixture.
2. Build Hugo/Hextra, check links, and audit the rendered site.
3. Deploy **only passing `main` builds** to GitHub Pages. Pull requests never deploy.

The public repository and Pages site are live. Passing pushes to `main` deploy automatically. For your own fork, select **Settings → Pages → GitHub Actions**, then run **CI and Pages** on `main` if needed. Only the deploy job has Pages/OIDC write permissions; there is no personal access token to configure.

See the [privacy review](docs/content/reference/privacy.md): shared firmware defaults and model IDs are public; custom credentials and per-device data stay private.

## Tools and tests

The repository retains the explicit authenticated uploader, public bootstrap templates, read-only metadata/network tools and offline firmware inspector. Use **uv** with the pinned Python environment:

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/build_public_bundle.py
```

The uploader sends only with its explicit write flag; the other tests use local fixtures and stubs. Follow the guide's backup, staging and verification order. Ordinary `uci commit` can write flash on the tested firmware.

Credentials, device backups, firmware, generated websites and build dependencies are ignored and excluded by the public allowlist. The [third-party notice](NOTICE.md) explains licensing. A normal reboot is verified; physical recovery, long streaming and IPv6 remain unverified.
