# Email Risk Alerts Setup

This repo stores subscribers in Cloudflare D1, serves subscription endpoints with Cloudflare Pages Functions, and sends daily threshold alerts from the GitHub Action.

## 1. Create the D1 database

Create the database with Wrangler or from the Cloudflare dashboard:

```sh
npx wrangler d1 create risk-metric-subscribers
```

Record the returned database ID. Apply the schema:

```sh
npx wrangler d1 execute risk-metric-subscribers --file infra/d1/schema.sql --remote
```

For a database created with the earlier subscriber-only schema, apply the
one-time migration instead:

```sh
npx wrangler d1 execute risk-metric-subscribers --file infra/d1/migrations/0002_release_alert_safety.sql --remote
```

## 2. Bind D1 to Cloudflare Pages

In the Cloudflare Pages project settings, open Functions, then D1 bindings. Add a production binding:

```text
Variable name: DB
Database: risk-metric-subscribers
```

## 3. Configure Resend and Pages variables

Create a Resend account and API key. In the Cloudflare Pages project environment variables, set:

```text
RESEND_API_KEY=<your Resend API key>
SITE_URL=https://risk-metric.pages.dev
ALERT_FROM_EMAIL=Risk Metric <alerts@your-domain.example>  # optional
ALLOW_LEGACY_PLAINTEXT_TOKENS=false
```

If `ALERT_FROM_EMAIL` is omitted, the code uses `Risk Metric <onboarding@resend.dev>`.

Important: with the default `onboarding@resend.dev` sender, Resend only delivers to the
email address that owns the Resend account. That is enough to test the pipeline and to
alert yourself, but before other users can subscribe you must verify a domain in Resend
(Domains → Add Domain, add the DNS records) and set `ALERT_FROM_EMAIL` to an address on
that domain in both the Pages env vars and the GitHub secrets/env.

## 4. Configure GitHub Action secrets

Create a Cloudflare API token with permission to edit D1 for the account. Add these repository secrets:

```text
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
D1_DATABASE_ID
RESEND_API_KEY
ALERT_TOKEN_ENCRYPTION_KEY  # optional but recommended; keep stable across Resend key rotation
```

Also add these repository variables (Actions → Variables):

```text
SITE_URL=https://risk-metric.pages.dev
ALERT_FROM_EMAIL=Risk Metric <alerts@your-domain.example>
```

`ALERT_FROM_EMAIL` may be omitted while testing with Resend's default sender. Keep
`SITE_URL` aligned with the deployed Pages origin so links in alert emails are valid.

The dispatch script exits successfully with a skip message until all four required secrets are configured.
Before querying subscribers it idempotently verifies the alert schema and adds
missing release-safety columns/tables. `ALERT_TOKEN_ENCRYPTION_KEY` encrypts the
per-delivery unsubscribe token needed for deterministic retries; without it,
the existing Resend key is used as the encryption secret.

Legacy plaintext token lookup is disabled by default. A short migration window
can be enabled with `ALLOW_LEGACY_PLAINTEXT_TOKENS=true`, but the compatibility
path is hard-disabled after 2026-10-01 even if the flag remains set.

## 5. Test subscription

After deploying Pages, submit a test subscription:

```sh
curl -i https://risk-metric.pages.dev/api/subscribe \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","buyThreshold":0.25,"sellThreshold":0.75,"website":""}'
```

Open the confirmation link from the email, then use the button on the landing
page. Confirmation and unsubscribe links do not mutate state on GET; their
forms submit the one-time token with POST. You can inspect D1 rows with:

```sh
npx wrangler d1 execute risk-metric-subscribers --remote --command "SELECT email, status, buy_threshold, sell_threshold FROM subscribers"
```

## 6. Test daily dispatch locally

Run the dispatcher against the real D1 database:

```sh
CLOUDFLARE_API_TOKEN=... \
CLOUDFLARE_ACCOUNT_ID=... \
D1_DATABASE_ID=... \
RESEND_API_KEY=... \
SITE_URL=https://risk-metric.pages.dev \
node scripts/send-alerts.mjs
```

The script validates the complete `data/web/v2` release and its `release_id`,
queries active D1 subscribers, sends Resend emails only for buy or sell zone
crossings, updates `last_zone`, and logs a summary. Deliveries have a
deterministic Resend idempotency key and pending/sent/failed state in D1. It
refuses to send from a mixed, modified, malformed, future-dated, or
more-than-two-days-old release.
