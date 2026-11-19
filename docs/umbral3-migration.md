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
