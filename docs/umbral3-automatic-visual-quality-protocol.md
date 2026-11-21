# UMBRAL 3.0 — consented automatic visual quality gate

Owner consent: 2026-11-22, future slots **2026-11-28 onward**. This is **not**
an owner image review, nor a modification of the immutable 84-frame signoff
made on 2026-11-21.

## Operation

1. Keep generating dated, numbered-placeholder full Reel candidates **privately**,
   with zero Meta permissions. Each candidate has an immutable index and a
   SHA-256-verified ZIP containing six original PNGs, voice, music, subtitles,
   cover, timeline and MP4. No image or video is copied to a public artifact.
2. The daily D+7 job attempts to independently score the newly generated
   candidate. It verifies exact private ZIP bytes and editorial story hash,
   six decoded 512×896 PNGs, frame uniqueness and contrast/exposure,
   original candidate flags, the six-shot timeline, cover and full bundle
   integrity. A separate pinned **CLIP ViT-B/32** model compares the six
   actual frames with their six shot prompts, a horror atmosphere caption
   and cheerful/neutral distractors.
3. Minimum pilot requirements: at least **4/6 relevant shots** ranked in the
   top three of the actual authored prompts, **4/6 horror signals** over
   neutral/cheerful by >=0.6 CLIP logit units; all six pass hard visual
   checks. These are intentionally conservative and must be calibrated
   against private human inspection. CLIP is imperfect: passing a model
   **does not guarantee** correct anatomy or perfect plot continuity.
4. Only a passing run may persist a **small private** automatic QA certificate,
   bound to the exact candidate bundle SHA, story SHA, six image SHAs,
   pinned model+revision and explicit thresholds. The record says
   `human_review: false`, `machine_approved: true`,
   `ready_to_publish: false`. A red run or missing model issues NO certificate.
5. On the civil date, only the trusted main workflow can use an OIDC-scoped
   token to re-read the immutable private certificate and index. On staging
   it restores the exact six scenes and matches their SHAs again, binds the
   actual official episode number, and reuses the existing Meta duplicate,
   intent, Pages, caption, audio and publication controls.
6. The legacy primary **yields the scheduled primary slot** for future
   auto-QA days; if the new gate declines, the independent legacy backup
   crons still serve the same 09:00 or 21:00 Madrid publication windows.
   Both official routes retain `umbral-instagram-official` concurrency.
   No experimental Meta POST is ever made for QA.

## Rollback and safety

- Set GitHub variable `UMBRAL3_AUTO_QA_ENABLED=false` to disable machine QA:
  the existing legacy primary takes over (the V3.1 owner-approved 22–27 Nov
  window retains its separate explicit consent).
- `UMBRAL3_LIVE_ENABLED=false` disables the V3.1 producer; legacy remains.
- `UMBRAL_META_PUBLISH_ENABLED=false` disables all official publishing.
- Machines never create `docs/visual_approvals` or owner-signoff JSON.
- Original 2026-11-21 board and all previous published receipts are immutable.
- Certificates require an actual private CLIP run; writing an arbitrary
  `quality_passed` or `visual_approved` in a private media file is rejected.
- A passing CI is **not** proof of seven live days; continue seven-day
  official-receipt monitoring. If model quality is aesthetically poor, turn
  the automatic route off and retain the legacy route while improving it.

The private two-slot 28-Nov pilot must complete and emit real certificates
before claiming automatic publication is active for those slots. GitHub
Actions CI alone tests code, not actual unseen frames or model score margins.
