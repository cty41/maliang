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
Existing hard-link aliases are rejected as immutable publication targets,
including aliases with publication-temporary filenames. When a destination has
multiple links, a publisher waits up to one second for concurrent creation-link
cleanup, then rejects it if the link count is still not one. Alias names are
never treated as proof of ownership, and unknown aliases are never deleted.
Idempotent publication requires a single-link destination before and after
reading its bytes; a stalled publisher or abandoned creation link fails closed
rather than permitting an alias. Hard links used internally for creation are
removed before publication returns successfully. If temporary cleanup fails,
publication reports an error even when the target has already been created;
it does not roll back or delete the published target or unknown aliases. If
publication was already failing, that original error and its cause are preserved.
A retained creation alias makes subsequent attempts fail closed after the same
bounded wait.
Contained reads still assume that an attacker cannot plant aliases in the trusted
root. Run against a caller-controlled root with operating-system permissions
that exclude untrusted writers; use a platform-specific directory-handle
sandbox when hostile concurrent mutation is in scope.
