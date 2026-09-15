# Synthetic provider lifecycle

This MIT-licensed fixture shows MaLiang's provider-neutral record boundary.
It does not call a real service and contains no source-project artwork.

- `success/invocation.json` records a request to a fictional offline provider.
- `success/delivery.json` binds that invocation to `delivery.png` by SHA-256.
- `failure/invocation.json` is a separate request.
- `failure/failure.json` records its retryable, structured failure.

A delivery and a failure are alternative outcomes, so they use distinct
invocations. Provider adapters may create these envelopes, but they cannot
approve their own artwork; project review policy remains a separate authority.
