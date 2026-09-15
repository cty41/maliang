# Security policy

## Supported versions

Security fixes are provided for the latest released 0.1.x version.

## Reporting a vulnerability

Please report vulnerabilities privately through the repository's GitHub
security-advisory form. Do not include confidential artwork, credentials, or
provider responses in a public issue. Expect acknowledgement within seven days.

MaLiang treats path containment, immutable publication, record binding, and
content hashes as security boundaries. A hash proves byte identity, not trust or
license status; callers must establish those separately.

Invocation `request`, delivery `metadata`, and failure `details` are designed for
persistent audit records. Never place API keys, access tokens, private prompts,
or other credentials in those fields; provider adapters must redact secrets
before constructing a MaLiang record.
