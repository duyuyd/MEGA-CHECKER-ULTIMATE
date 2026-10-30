# QA 10.0.0 — Data Intelligence foundation

## Automated coverage
- Email-only and email:secret/email|secret parsing.
- Valid/invalid address counts and exact duplicate counting.
- Summary report contains no secret values.
- Oversized physical lines are skipped safely.
- Invalid mode and line-size bounds are rejected.
- Bounded batch scheduler caps worker count at 32 and in-flight futures at 128.

## Security properties
- Offline only: no HTTP, OAuth, login, password-reset, cookie, or account mutation requests.
- Secret components are handled transiently in the current input line and not persisted, logged, or exported.
- Temporary deduplication database contains normalized email identifiers only and is deleted after the audit.
- Report contains aggregate counts and domain/provider distribution.

## Limits
- Email syntax validity does not prove mailbox existence or account ownership.
- Dataset audit does not verify passwords or account credentials.
- Domain/provider distribution is based on the built-in provider map.
