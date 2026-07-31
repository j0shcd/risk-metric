# Use a lightweight alert delivery ledger

Threshold alerts will use a small D1 delivery ledger keyed uniquely by subscriber, Release, and entered zone. The scheduled dispatcher creates a pending Alert Delivery, sends with the matching deterministic Resend idempotency key, records the provider identifier and outcome, then advances subscriber zone state. Explicit retry rules handle pending or failed deliveries; no queue, dedicated worker, provider-webhook system, or exactly-once claim is warranted for this side project.

## Security and safety boundary

- Confirmation and unsubscribe links render a landing page; a POST performs the one-time mutation so automated link scanners cannot change state through GET.
- Signup keeps the honeypot and adds a per-address confirmation cooldown plus conservative global send ceiling. Turnstile is added only if actual bot abuse appears.
- Responses do not reveal whether an address is already subscribed.
- Confirmation and unsubscribe tokens are high-entropy, single-use, rotated when appropriate, and stored as hashes rather than reusable plaintext.
- All database access remains parameterized; email and HTML content is validated/escaped; unsupported methods and content types fail closed.
- No raw IP history, user accounts, queue, or additional always-on service is introduced.
- Operational delivery rows expire after roughly one year; they are not prospective model evidence.
