# Third-party notices

- dnspython 2.8.0 is bundled under `vendor/dns/`. It is distributed under the ISC License; see `vendor/DNSPYTHON_LICENSE.txt`.
- idna 3.17 is bundled under `vendor/idna/`. It is distributed under the BSD 3-Clause License; see `vendor/IDNA_LICENSE.md`.
- certifi 2026.5.20 is bundled under `vendor/certifi/`, with its Mozilla CA certificate bundle; see `vendor/CERTIFI_LICENSE.txt` (MPL 2.0).
- The Public Suffix List snapshot is in `data/public_suffix_list.dat`, covered by Mozilla Public License 2.0; see `LICENSE-MPL-2.0` and `data/README_PSL.txt`.
- Optional runtime dependency: `dkimpy` 1.1.8 is installed separately only when full DKIM cryptographic verification is requested (`requirements-dkim.txt` / `scripts/install_dkim_termux.sh`). It is not bundled in the source ZIP. Upstream license notice is the Zlib-style notice in the dkimpy source distribution; project: https://pypi.org/project/dkimpy/.
