+++
title = 'Build & contribute'
description = 'Preview the Hugo/Hextra site, run the host checks and prepare a clean public snapshot.'
weight = 30
type = 'docs'
+++

Edit the website documentation in `docs/content/`. The root README introduces the repository. Put step-by-step instructions in the guides, and technical background and test history in the reference pages.

## Preview the website

Get the source, then run the preview:

```sh
git clone https://github.com/arunoruto/c200-local.git
cd c200-local
uv sync --locked --group analysis
uv run --locked python scripts/site.py prepare
uv run --locked python scripts/site.py serve
```

Open `http://localhost:1313/` on the same computer. The server listens only on that computer. If you run it on a remote host, forward the port through SSH or your usual preview setup.

`prepare` fetches checksum-pinned Hextra and search assets. On Linux amd64/arm64, it also prepares Hugo if no installed executable is available. On other systems, install Hugo first. The tested versions are **Hugo 0.170.0**, **Hextra 0.13.0** and **FlexSearch 0.8.143**; URLs and hashes live in `docs/dependencies.json`. No Node or Go toolchain is needed for this setup.

The theme, downloaded tools, local search library and generated output are ignored. Search is served from the built website, not loaded from a third-party CDN by the browser. There is no analytics configuration.

## Build and check static HTML

```sh
uv run --locked python scripts/site.py build
uv run --locked python scripts/site.py check
```

Output is `docs/public/`. The build checks generated local page/asset links and verifies that the two bootstrap downloads match `camera/`. Downloads contain those public templates and the public reference/allowlist metadata. You can also download the [result summary as JSON](/results.json).

To reproduce the published project URL:

```sh
uv run --locked python scripts/site.py build --base-url https://arunoruto.github.io/c200-local/
```

For a fork or another host, substitute its deployment URL and keep the trailing slash. The same build can be hosted by any static web server.

## GitHub Pages

The [public repository](https://github.com/arunoruto/c200-local) and [documentation site](https://arunoruto.github.io/c200-local/) are live. Passing `main` builds deploy automatically through [CI and Pages](https://github.com/arunoruto/c200-local/actions/workflows/docs.yml).

To deploy your own fork:

1. Fork the public repository, or create a repository from the **audited public export**, not the working research directory.
2. Choose **Settings → Pages → Build and deployment → GitHub Actions**.
3. Run **CI and Pages** from the Actions tab on `main`. If the first push ran before Pages was enabled, rerun after selecting that setting.

Every pull request and `main` push runs source/tracked-file checks and the host tests. CI downloads only the checksum-pinned stock 1.1.15 fixture to enable the optional offline tests; it never contacts a camera. The build job prepares the pinned website dependencies, validates root/project-path links and audits rendered output before any Pages artifact is uploaded.

Only successful pushes or manual runs on `main` upload/deploy. Pull requests build and validate without configuring Pages, uploading a Pages artifact or deploying. Checkout credentials are not persisted. Only the final deploy job receives `pages:write` and `id-token:write`; it uses GitHub's built-in token/OIDC and the `github-pages` environment. You do not need a personal access token.

The deployment uses the Pages base URL returned by GitHub, including a repository subpath or configured custom domain. PR checks use a project-style preview URL. Action revisions and uv/Hugo/Hextra versions are pinned. The workflow is in `.github/workflows/docs.yml`. Local builds stay on your computer until you publish them.

[GitHub's custom Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) covers the platform setup.

## Edit the content

| Location | Purpose |
|---|---|
| `docs/content/guide/` | Downgrade, initial-shell reference, persistent Telnet and acceptance checks |
| `docs/content/reference/` | Mechanism, results/limits and source credits |
| `docs/layouts/` | Project landing page and small Hextra overrides |
| `docs/assets/css/custom.css` | Project styling |
| `docs/static/results.json` | Selected non-identifying acceptance results |
| `camera/` | Public example-address bootstrap templates |
| `scripts/` and `tests/` | The uploader, analysis/publication tools and host checks |

Keep the links to the external shell-access guides in `docs/content/guide/initial-shell.md`. Those guides cover getting the first shell; this project covers keeping access after reboot.

Use example addresses instead of a real camera's address. Describe how each result was tested: on the camera, in a simulation on a computer, or not yet tested. A compatibility match or accepted HTTP upload alone does not confirm that a firmware update completed.

## Run the host tests

```sh
uv run --locked python -m unittest discover -s tests -v
```

The tests use fixtures and stubbed network/firewall/listener commands. They do not contact a camera. Optional exact-firmware cases skip when the reference is absent; [validation](reference/validation.md) explains how to enable them.

The analysis tools can verify downloaded reference files, inspect firmware offline, check TCP listeners, and collect or reanalyze local API metadata. Follow the downgrade and permanent Telnet guides for the main workflow.

## Prepare the public source

```sh
uv run --locked python scripts/build_public_bundle.py
uv run --locked python scripts/build_public_bundle.py --build
```

In a clean Git checkout, add `--check-tracked` to reject tracked files outside the list. After building, `--site-dir docs/public` also audits rendered output. The generated `SHA256SUMS` file belongs to the export and is ignored by Git.

`PUBLIC_FILES.txt` lists the website source, guides, original tools and tests, and license files that can be published. The audit rejects excluded paths, symlinks, missing/binary files, known custom password contents, unit/account fields in public JSON and several common secret formats. The documented stock root default is permitted; see the [privacy review](reference/privacy.md). It identifies files without printing secret values; it cannot recognize every possible secret.

The tool writes the source directory and tarball under ignored `work/public-release/`, with `SHA256SUMS`. Use that checked export when publishing from a workspace that also holds research files or device data. Build dependencies are fetched separately by `site.py prepare`.

Credentials, `HANDOFF.md`, device reports, saved configuration, partition dumps, firmware, ART candidates, transfer archives and third-party PDFs stay private. Existing ignored files are not made safe merely by adding `.gitignore` after they have entered Git history.

## Licensing

Original scripts and documentation use the [MIT license](/licenses/project.txt). Third-party firmware, reference archives, dependencies and external research retain their own licenses. Firmware and device dumps are not distributed.

The generated site uses Hextra under [its MIT license](/licenses/hextra.txt) and FlexSearch under [its Apache-2.0 license](/licenses/flexsearch.txt). Preparation preserves those notices in the static output. See the [source credits](reference/sources.md) and repository `NOTICE.md`.
