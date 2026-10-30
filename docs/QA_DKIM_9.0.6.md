# QA DKIM 9.0.6

- The generic common-selector list is unchanged.
- `gmail.com` additionally probes provider-specific candidates `20251104`, `20230601`, and `20221208`.
- `20251104` is grounded in publicly available Gmail message headers that continued to show `d=gmail.com; s=20251104` through September 2026. This is an observed selector hint, not a guarantee for every account or future messages.
- `20230601` and `20221208` are included to identify historical revoked-key TXT records reported on 2026-09-15.
- Provider-specific candidates are not queried for unrelated domains.
- A negative probe result is `not_found_in_tested_selector_hints`; it is not a claim that Gmail does not use DKIM.
- The DKIM resolver reads DNS records only. It does not verify the cryptographic signature over a complete email.
