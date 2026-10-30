# QA DKIM 9.0.4

- Parse `DKIM-Signature` headers including folded continuation lines.
- Extract only the `d=` signing domain and `s=` selector; never return or log `b=` signature data.
- Query exact `selector._domainkey.signing-domain` TXT owner name.
- Distinguish `present`, `revoked`, `not_found`, `invalid_record`, and `unknown`.
- Common selector scan remains heuristic and does not claim exhaustive absence.
- `dkim --headers-file` reads a local file up to 1 MiB; the contents are not transmitted.


Status interpretation:

- `present`: a syntactically recognizable DKIM1 key record with non-empty `p=` was returned.
- `revoked`: the DNS key record contains an empty `p=` value.
- `not_found_for_supplied_selectors`: all supplied selector names were definitively absent.
- `invalid_record`: TXT data exists at the selector owner name but is not a usable DKIM1 key record.
- `unknown`: resolver configuration, timeout, or DNS errors prevented a conclusion.
