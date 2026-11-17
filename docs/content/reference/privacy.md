+++
title = 'Privacy review'
description = 'What belongs in the public repository and how source and website checks enforce that boundary.'
weight = 40
+++

The publication review on 17 November 2026 found **no device-specific secrets in the reviewed public source or generated website**. The working research directory still contains private credentials, device reports, configuration/partition backups and transfer archives. They are intentionally outside `PUBLIC_FILES.txt` and must remain outside the GitHub repository.

## Public references are not personal secrets

The stock C200 Linux root password, `slprealtek`, is already documented in the [original public C200 research](https://github.com/nervous-inhuman/tplink-tapo-c200-re#default-root-password-and-u-boot-console). The audit permits that exact value. It does not treat every password or account hash as public.

The same distinction applies to stock firmware checksums and model/OEM/hardware compatibility identifiers extracted from public stock images. Those shared values are useful for identifying the right image and testing the comparisons. They are different from a unit's device ID, serial, MAC or cloud account.

The example addresses in the guide and bootstrap are generic. Public NTP and protocol multicast addresses are protocol configuration, not personal identifiers. The result summary contains selected non-identifying status, codec, resolution and timing observations rather than raw API responses.

## What was checked

- Every file selected for the public source package.
- Personal filesystem paths, email/MAC addresses and the actual camera address.
- The actual unit identifiers and custom credential values from the retained local metadata, compared in memory without printing them.
- Generated HTML, Markdown, JSON, JavaScript and other static assets.

No matches for the reviewed private values were found. This does not require publishing the private reference values or putting them in CI secrets.

## Automated checks

From a clean Git checkout of the public source:

```sh
uv run --locked python scripts/build_public_bundle.py --check-tracked
uv run --locked python scripts/build_public_bundle.py --site-dir docs/public
```

The tracked-file check rejects any committed path outside the explicit public allowlist, including accidentally forced credential files. The normal source audit rejects excluded paths, symlinks, non-text source and several private-key/token/account-hash formats. When local credential files are available, custom values are compared in memory; the documented shared default is exempt.

Public JSON is also checked for unit/account fields such as device IDs, MACs, SSIDs and session tokens. Shared model/OEM fields remain allowed. The rendered-site audit applies the content checks to generated output too, while allowing normal binary assets such as icons.

CI runs these checks and the host tests before building and deploying. The website builder separately refuses unlisted source/static inputs and verifies the public bootstrap downloads. The deployment artifact contains only `docs/public/`.

The checks do not recognize every possible secret or remove data already pushed into Git history. Review new material, keep raw reports private and start the repository from the audited public export. Never add a credential file simply because its current contents happen to be a stock default: that same file could later contain a custom password.
