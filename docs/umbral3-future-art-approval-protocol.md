# UMBRAL 3 · Per-slot future visual signoffs (append-only)

This is an **implemented release contract**, not an approval of any future image.
The 2026-11-21 owner board and its 14 existing signoffs remain unchanged.
New private candidate ZIPs always remain `visual_review=not_performed` and
`ready_to_publish=false` until exact independent owner review exists.

## Independent evidence required for every new date and slot

1. The private generation pipeline must complete and independently verify the
   original story SHA-256, the immutable private ZIP SHA-256 and each of six PNG
   SHA-256 values. The output is a private **candidate**, not publication-ready.
2. A **real owner-reviewed** private contact board must be recorded with its
   exact SHA-256. A structural/semantic/image quality score does not constitute
   this review. Unseen images cannot be signed off by a blanket authorisation.
3. Only after explicit review of that exact board, a separate immutable file
   `docs/umbral3-future-signoffs/YYYY-MM-DD[_09].json` may be created with
   schema below and a separate matching
   `docs/visual_approvals/YYYY-MM-DD[_09].json` approval record. These records
   are never emitted or auto-written by the generator or private runner.
4. `scripts/umbral3_release_policy.py` validates the complete signoff identity
   and the independent approval; `scripts/umbral3_approved_restore.py` verifies
   remote pointer, ZIP and actual six PNG bytes again before late-numbered
   finalization. A missing or mismatching record leaves the old publisher in
   control. A Reel is not approved merely because its still images are approved.
5. Meta publication still requires the existing official exclusive lock, all
   unresolved intents reconciled, the current Madrid slot/date, exact HTTPS media
   readback, and only one irreversible publish POST. Failed readback does not
   permit another POST. Never backfill a past date.

## Future signoff fields

Required exact keys:
- `version: 1`, `kind: umbral3-explicit-owner-future-signoff`,
  `owner: fedry23`
- `date`, `slot` (either `09` or `21`), `title`, `reviewed_at`
- `reviewed_board_sha256` (actual independently viewed private board)
- `backend` (pinned approved backend name)
- `story_sha256`, `private_candidate_bundle_sha256`
- `scene_sha256` (exactly `scene_00.png` through `scene_05.png`)
- `record` (canonical relative path to the independent owner approval)

The corresponding owner approval record uses
`scripts/umbral3_visual_approval.py`'s existing strict schema. Its
`reviewed_at` must match the future signoff; `notes` must mention both
the exact reviewed board SHA and exact candidate ZIP SHA. Both documents must
match the current editorial story, date/slot and every restored PNG hash.

**No future signoff files exist or are approved merely from this contract.**
The owner must inspect the actual future scenes first. Do not overwrite old
approvals, delete private candidates or infer signoff from a generator's output.

## Recovery and rollback

If a future visual review fails, leave the candidate private and never
publish it via V3.1. Existing legacy 09:00 and 21:00 workflows remain
separate, with the shared `umbral-instagram-official` lock and official
receipts. The V3.1 live route remains disabled unless explicitly enabled
for production after release gates; `UMBRAL_META_PUBLISH_ENABLED=false`
is the emergency stop. To roll back from V3.1 to legacy, disable the V3.1
route and confirm the original official schedules are active **before** any
new Meta POST. Never clear an unresolved `docs/pending` intent merely to
force a retry; reconcile against the official media list first.
