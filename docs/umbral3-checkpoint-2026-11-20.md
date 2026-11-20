# UMBRAL 3.0 — checkpoint 2026-11-20 (post episode 15)

This is an evidence ledger, not a completion declaration. Keep official publishing at 09:00/21:00 Europe/Madrid; never repeat an uncertain Meta POST. No new paid services, no experimental public media, no changes to Curio25 or JARVIS.

## Verified production incident

- Official generation 09:00 run 44695086362 started 07:27:21 UTC, failed before render in 4 legacy fixed-number tests; scheduled 00:17 UTC. Evening generation 44715285721 started 09:59 UTC, same 4 legacy test errors; scheduled 02:17 UTC. Production hotfix 97d158e7376e21035cfa4dc7f402c894c27b9e2e already addresses that incompatibility. Cron delays remain externally dependent.
- Episode 14, La cámara de frío, published 15:24:28 Madrid, receipt docs/published/2026-11-20_09.json. Episode 15, La cuerda de regreso, confirmed run 44812182234, local regeneration after missing successful same-day artifact, published 21:41:51 Madrid. Receipt docs/published/2026-11-20.json verifies media 18124716275471761, permalink https://www.instagram.com/reel/Df-iX8FvhzX/, matched cover. Do NOT republish.
- Main official receipt history synced into integration via PR #21 (049b7c1f71f0f01e15774b2fc45d82b905e8dacd). Run 44815106155 regression job 136561375184: 124 tests passed, next official episode 16.

## Independent reliability release

- PR #20 (fix/validated-artifact-recovery): ports same-day fallback in both staging scripts and regression tests without any experimental rendering or Meta changes. Production-baseline run 44814314633: 86 unit tests and official receipt inventory passed, next episode 16; real-media staging test still in progress at last check. Do not merge until independent run completes successfully and current head/base are rechecked. Revert commit/PR if post-merge regression; preserve all publication receipts and history. Do not replay a publishing workflow as a rollback.
- PR #18 remains draft pending real private visual approvals, storage and production release checks.

## Editorial reserve

- 14 slots covering 21–27 November authored on integration (12 new stories, plus storyboard metadata for the two existing 21 November stories). All 14 have six distinct planned shots and 140–170 words, tested by tests/test_umbral3_editorial_reserve.py on run 44815106155. No official numbers preallocated.
- Commits: 8d307bceaecc2d4630bc18682a506cb1d73ab19b, 91080ce9834dfc7c17c03ecc9464ef0e982bd9b2, 25efdd311b9f460675853fd07e856e4474878c8f, 25a4a3e307d40329887878f4a64c90423522df97, b8e7e9304cc67e3ba1b0e7b3e93fcd1496fb6786.
- Editorial QA is structural, not proof that images match, and not a full reserve of ready videos. Main catalog has not yet received the 12 new stories. Deploy editorial-only changes after isolated production checks, independently of visual experiments.

## Next visual/storage gate

- Isolated benchmark run 44815232445 tests pinned OpenVINO SDXL INT8 (OpenRAIL++) and FLUX Schnell INT8 (Apache-2.0) on standard CPU runners, without credentials or public uploads. It measures resource feasibility and output dimensions, not visual approval. Inspect job logs, actual peak RSS and per-shot elapsed time; failure is evidence, never an excuse to lower quality silently.
- Dropbox dedicated app-folder OAuth still required for real private evidence and reserve readbacks. Connector authorization for ChatGPT is not runner OAuth. Do not expose secrets or publish private trial artifacts to this public repo.
- Need private storage connectivity/quota, bounded reserve retention, real full-media packaging and late-numbering composition, three retained private test Reels with direct visual review, a live 14-Reel reserve with recovery, and seven observed days of production after deployment. No completion claims before these checks.
- Automation read attempts still return 404, no schedules changed and no new automation created. Existing Windsor snapshot for episode 14 only, no paid refresh; do not make learning decisions on a single Reel.

## Continuation order

1. Check live official receipts and jobs, then complete and merge only PR #20 if fully green.
2. Sync main to integration and verify latest regression.
3. Promote the editorial backlog independently through production QA (do not alter tomorrow's stories).
4. Resolve private storage authorization, benchmark visual candidates and retain three private full renders for direct inspection.
5. Complete late-numbering assembly, persistent 14-Reel queue, restoration test and monitored rollout. Keep PR #18 draft until all release conditions are met.
