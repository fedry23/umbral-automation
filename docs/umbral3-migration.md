# UMBRAL 3.0 — migration stage 1

Branch-only experiment; main remains unchanged. No Meta access, Pages upload,
or publication. Existing stories are unchanged and retain their old timing
until explicitly migrated. A version-1 storyboard declares a continuity bible
(short literal English visual anchors), one shot for each scene, exact Spanish
narration partition, camera, action, references and a concise English prompt.
The renderer fails before expensive image generation if narration cannot map
to complete speech cues, and rejects prompt truncation. Shot timeline is
written locally. This is structural alignment, not proof that the generated
image actually depicts the action or that characters are visually consistent.

Known issues: current production chooses the first technically valid frame;
technical QA cannot verify semantics/anatomy and CLIP is still experimental.
Current staging filters runs by local date, preventing a true seven-day
pre-render queue. Current numbering is speculative and must be redesigned
before sealing final numbered media days in advance. Public repository Actions
artifacts are not private; experimental media must not be uploaded there
without a private inspection route. No production migration until tests,
three real private renders and direct visual review, license/cost verification,
rollback and publication reconciliation are complete.

## Editorial fixtures
Three fictional stories for isolated testing: rail infrastructure, hotel room, woodland surveillance. Tests exercise real speech segmentation with synthetic timestamps, not real TTS timing or visual quality. No publish dates, official numbering or public media artifacts. Full renders and visual review remain required.

## Isolated full-render gate
Three fixtures now have an explicit media-only render entry point. Each runs separately with a bounded timeout, one at a time, no Meta environment, no publishable date, no public artifact, and automatic temporary directory cleanup. It emits technical reports, including image QA and actual shot durations, but does NOT establish visual approval. A private media inspection route is still required; do not claim review from scalar metrics. Official render selection and output naming are preserved by the shared function.

## Visual reserve contract (not yet wired to production)
The 7-day/14-slot scheduler uses Madrid civil time and UTC timestamps through DST. A visual asset manifest binds exactly the authored story and renderer recipe to six validated portrait PNGs with hashes and byte counts, independent of the official episode number. Revalidation rejects stale or missing media, hash changes, duplicate images and wrong slots. The state is explicitly visual_assets_prepared, never a full ready Reel or visual approval. Rendering/remote object storage, lock/CAS persistence, visual approval, late numbering, voice/branding composition, and deployment remain pending. Never persist reserve media to a public repository or reuse a stale manifest. Existing production paths are unchanged.

## Private storage integration
Explicit preparation uses a pinned model revision, code hashes, recipe and immutable content-addressed bundle. Local filesystem storage supports tests and persistent machines; Dropbox app-folder backend uses dedicated OAuth refresh credentials and atomic add without overwrite or sharing links. Read back the winning object before declaring prepared; ambiguous writes are reconciled. The shared renderer accepts an explicit reserve store/slot and verifies archived shots before composition. Production defaults to existing route. Dedicated OAuth credentials must be configured separately in Actions; no credentials are asserted configured. Tests exercise local persistence and simulated network failure, not real Dropbox authorization. Storage quota, retention, review approval, technical profile matching, remote round-trip and scheduled preparation remain to validate before activation.
