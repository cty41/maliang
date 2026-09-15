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

## Filesystem threat model

Repository roots and their parent directories must not be concurrently renamed
or rewritten by an adversary while MaLiang is reading or publishing. MaLiang
rejects lexical traversal, visible symlinks and Windows reparse points, and it
rechecks path components around I/O. Those portable checks reduce accidental
and ordinary link redirection, but pathname APIs cannot eliminate check/use
races against an attacker who can mutate the directory namespace concurrently.
Existing hard-link aliases are rejected as immutable publication targets; hard
links used internally for creation are removed before publication returns.
Contained reads still assume that an attacker cannot plant aliases in the trusted
root. Run against a caller-controlled root with operating-system permissions
that exclude untrusted writers; use a platform-specific directory-handle
sandbox when hostile concurrent mutation is in scope.
