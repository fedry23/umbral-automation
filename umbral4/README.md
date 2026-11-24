# UMBRAL 4 — isolated development, NOT authorized for live publishing

## Evidence 2026-11-24
- Base e5b279b50d5a2974e7419361c5328cc100882d78. Main README describes older one-slot operation; AGENTS.md absent; 34 workflow definitions.
- 23 Nov 09 receipt episode 20: 09:07:24 CET. 23 Nov 21 episode 21: 24 Nov 07:12:32 CET, official readback, media 17997375906063444. Retain historical pending evidence; never delete to force retry.
- 24 Nov 09 receipt and pending missing at audit. Run 45332602802 cancelled. Run 45323011560 reported live evening release in progress (shared lock), do not cancel blindly. Run 45226556976 returned success with legacy selected=false and actual publisher skipped.
- Refill run 45329954736 failed: continuity anchor1 missing. Existing public path can install models, regenerate, re-encode, build Pages, then wait for Meta. All these must move ahead of the deadline.
- Source: GitHub Actions runs and docs/published on main. No live API query performed by this branch.

## Architecture / safety boundary
Editorial -> audiovisual -> private validated MP4+JPEG+storyboard manifest -> dated queue -> prehost and prepare container -> single publisher. Supervisor and external scheduler only invoke the same publisher. Learning only updates reviewed editorial recommendations.

Core module publisher.mjs has no I/O except explicit adapters. One account-wide CAS ledger serializes irreversible intents. An unresolved intent blocks future posts; no write retries on uncertain results, including 429/500. Readback uses exact caption marker, owned media, product type, permalink, time and ID. Numbering increments only on verified receipt. All test fixtures are fake. There is intentionally no live endpoint, cron or secret binding.

Storage candidate: Cloudflare Workers Free + SQLite-backed Durable Object, with one authenticated account object and transactional CAS. Existing HF private bucket candidate for reserve; staging public video and cover before due time. No account, deployment or quota confirmation yet. Archive immutable receipts before ledger size threshold; implement and test import of historical receipts and a complete calendar (no holes) before activation. Store CAS adapter is not deployed.
Primary scheduler candidate: Cloudflare Cron (UTC, civil slots Europe/Madrid). Backup candidate: authenticated cron-job.org or existing ChatGPT supervisor calling same endpoint, not independent Meta POSTs. GitHub Actions only for render, CI and optional dispatch to same endpoint; GitHub warns scheduled jobs can be delayed/dropped. Verify provider account availability and secret handoff prior to choice. No purchases.
- https://developers.cloudflare.com/durable-objects/platform/pricing/
- https://docs.github.com/en/actions/how-tos/troubleshoot-workflows
- https://cron-job.org/en/faq/
- https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api

## Gates
No production migration until actual reserve of 14 finalized videos, verified hashes, durable ledger integration, prepared container lifecycle, authenticated scheduler, historical import, rollback and no active/ambiguous legacy attempts. All critical integration tests must pass. Initial proposed tolerance +5 min, never early; late recovery counts as a miss in the 28-consecutive-publication acceptance test. No claims of a guaranteed third-party SLA.

## 24 Nov second development session
- Added ledger.mjs: civil calendar, immutable archival, atomic rollover, import of historical files, duplicate media/number checks. In the baseline 17 receipt files include 13 consecutively numbered official episodes 9–21, plus older/experimental receipts. Older receipts without verified readback are preserved but not upgraded to verified. Import is a snapshot only; fresh reconciliation and updated cutover date are required.
- Added prepare.mjs: verified hosting attestation and early container creation, isolated from heavy generation. No automatic repeat of an uncertain creation.
- Added worker.mjs and wrangler.toml: single Durable Object route for both scheduler and authenticated backup, with disabled default and no cron configured. Deployment and account access have NOT been established. Cloudflare free Worker CPU limits require an actual integration/load check; no quota or cost guarantees.
- GitHub Actions integration run 45381168531 succeeded: actual historical snapshot, mocked transactional store and Meta, 28 simulated publications, rollover and restart. This is not the 28-live-publication acceptance test.
- Next gates: authenticated provisioning/ingress, fresh historical reconciliation, byte-level hosting verifier, real Durable Object tests, immutable storage and final 14-video inventory, safe recovery of old ambiguous intents, long-history Meta pagination, independent scheduler access and production switch. No actual media was rendered by this session.
