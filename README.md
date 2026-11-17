# C200 Local

[Live documentation](https://arunoruto.github.io/c200-local/) · [Repository](https://github.com/arunoruto/c200-local) · [CI and deployment](https://github.com/arunoruto/c200-local/actions/workflows/docs.yml)

Downgrade **Tapo C200 V2** to stock **1.1.15**, make normal Telnet login survive reboot, and preserve **RTSP and ONVIF with the cloud blocked**.

The setup was verified on one V2 camera on 17 November 2026. Original code and documentation are [MIT licensed](LICENSE). Firmware and private device data are not distributed.

## Follow the guide

Start with [prerequisites and setup](docs/content/guide/getting-started.md).

1. [Downgrade from 1.3.17 to 1.1.15](docs/content/guide/downgrade.md).
2. [Get a root shell](docs/content/guide/initial-shell.md) using the external guide and author's blog post.
3. [Make Telnet permanent](docs/content/guide/permanent-telnet.md).
4. [Verify both streams, ONVIF and local access](docs/content/guide/verify-streams.md).

For common failures, see [troubleshooting](docs/content/guide/troubleshooting.md).

The documentation is in **docs/** and uses Hugo with the **Hextra** theme. Read [how it works](docs/content/reference/how-it-works.md), [what was tested](docs/content/reference/validation.md), and the [source credits](docs/content/reference/sources.md) for the background and results. The guides explain which steps were tested on the camera and which were tested only on a computer.

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

The repository includes the authenticated firmware uploader, startup scripts, read-only device and network tools, and an offline firmware inspector. Use **uv** to run the tests and source checks in the pinned Python environment:

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/build_public_bundle.py
```

The uploader requires its write flag before sending firmware. The tests use local files and simulated services. Follow the guide's backup, trial and verification steps in order. Ordinary `uci commit` can write flash on the tested firmware.

Credentials, device backups, firmware, generated websites and build dependencies are ignored and excluded by the public allowlist. The [third-party notice](NOTICE.md) explains licensing. A normal reboot is verified; physical recovery, long streaming and IPv6 remain unverified.
