# Replace email alerts with public JSON

Publish two static version 1 JSON files after each daily refresh: the latest
reading and its four component contributions, and their finite daily history.
Use the dashboard's calculation functions and release identity. Provide public
cross-origin reads without a key. There is no RSS, email delivery, server code,
or user data. This supersedes [0005](0005-use-a-lightweight-alert-delivery-ledger.md).

## Why

Free-tier quotas and shared-account limits make delivery infrastructure a poor
fit for this project. Static files avoid personally identifiable information
and a bot-accessible signup endpoint. The evidence does not validate fixed
thresholds as buy or sell signals, so users bring their own rules rather than
receiving a notification that could imply an actionable recommendation.

## Consequences

- We send no notifications; users build their own scripts or automations.
- Version 1 fields only get added, never renamed. Breaking changes require a new version.
- Values run from 0 to 100 and describe the market against its own history.
- Low coverage or a missing current reading produces null latest values with
  an unavailable status, rather than an apparently usable current reading.
- Both files regenerate during the Pages build from the same immutable release
  as Today. They require no account, delivery provider, or persistent user store.
