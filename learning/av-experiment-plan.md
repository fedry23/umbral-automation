# UMBRAL — audiovisual experiments (2026-11-18)
  
One variable at a time. The current production baseline remains unchanged until
the exact code revision and each challenger pass the private validation gate.

| Experiment | Control | Challenger |
| --- | --- | --- |
| music-balance-v1 | Original mix | Music gain 0.85, same narration |
| voice-speed-v1 | 1.08 | Story-only 1.04; brand sections unchanged |
| camera-motion-v1 | Previous zoom | Progressive push to max 1.08 |
| visual-tone-v1 | Original colors | Bounded cooler grade on each scene |
| subtitle-outline-v1 | Outline 3 | Outline 4; same text, timings, font and placement |

The film grade is not evidence of character identity or narrative continuity.
Kokoro pronunciation and subtitle alignment remain model-dependent; a decoded
waveform or valid ASS file does not prove natural speech or exact word alignment.
No claim of higher quality or engagement from a successful build alone.

## Production rules

- Keep `learning/technical-policy.json` in hold until full challenger render
  validation. Once tested and no concurrent editorial experiment exists, select
  one experiment and mode experiment only. Never use promoted just to test live.
- Record each actual assignment by verified receipt `technical_profile`, slot,
  duration and media ID. Never infer assignment from catalog episode numbers.
- Collect official metrics at comparable observation ages (166–170 hours after
  publication); record source, retrieval time, cache/freshness status and raw
  values. Missing or contradictory data is not zero.
- Windsor.ai free retrieval may be cached and Meta metrics may be delayed up to
  48 hours (https://developers.facebook.com/documentation/instagram-platform/reference/instagram-media/insights).
  This limits causal inference. Use dated snapshots and never imply precise
  viewer-level retention. Exclude observations with unknown or incomparable
  age from automatic decisions; record them separately for descriptive analysis.
- Freeze editorial rules across technical arms; record protocol and avoid
  simultaneously running opening-hook experiments.
- Use scripts/technical_learning.py evaluate(rows, experiment) with verified
  observations from both slots. At least 10 posts and 500 reach per arm plus
  3 observations per slot/arm; the decision is a conservative heuristic.
  No promotion solely on likes, views, competition or synthetic unit tests.
- Compare experiments to the unchanged baseline. Do not silently stack
  challengers; a later combined profile needs new baseline and render validation.
- On quality failure, insufficient evidence or uncertain publication state,
  keep the established baseline. Never retry an uncertain POST.
- Competitor public page descriptions and engagement figures are contextual,
  not measured private retention or direct audiovisual inspection.
