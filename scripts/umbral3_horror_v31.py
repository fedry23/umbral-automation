"""Private follow-up to Terror v3: authored impossible beats come FIRST.

The owner-approved six-shot bus-stop v3 prompts and immutable v3 archives are
not modified. This explicitly opt-in direction has a separate backend namespace
and does not authorize publishing or auto-approval.
"""
from scripts.storyboard import validate_storyboard
from scripts.umbral3_horror_direction import BEATS
from scripts.umbral3_horror_v3 import TITLE, directed_prompts_v3

VERSION = "horror-v3-1"


def directed_prompts_v31(story, tokenizer):
    shots = validate_storyboard(story)
    if len(shots) != 6:
        raise ValueError("Six storyboard shots are required")
    # Exact owner-reviewed direction for the bus-stop story is sacrosanct.
    if story.get("title") == TITLE:
        return directed_prompts_v3(story, tokenizer)
    beats = BEATS.get(story.get("title"))
    if beats is None or len(beats) != 6:
        raise ValueError("Uncurated supernatural beats: private v3.1 review is required")
    continuity = story["storyboard"]["continuity"]
    anchor = continuity.get("anchor0")
    if not isinstance(anchor, str) or not anchor.strip():
        raise ValueError("Missing common storyboard setting")
    prompts = []
    for index, (shot, anomaly) in enumerate(zip(shots, beats)):
        # SDXL's short CLIP context must contain BOTH the authored action and
        # the actual paranormal event. Truncation would reproduce the
        # attractive-but-non-horror contact sheets we rejected.
        action = shot["action"].strip(" .")
        anomaly = anomaly.strip(" .")
        if not action or not anomaly:
            raise ValueError("Empty physical or impossible horror beat")
        core = f"{anomaly}. {action}."
        candidates = (
            f"Photoreal cinematic supernatural horror, vertical frame. {core} "
            f"Same {anchor}. Dark shadows, single cold light. No text.",
            f"Cinematic supernatural horror photo. {core} "
            f"Same {anchor}. No text.",
            f"Cinematic horror photo. {core} No text.",
        )
        selected = next((s for s in candidates
                         if len(tokenizer(s, truncation=False).input_ids)
                         <= tokenizer.model_max_length), None)
        if selected is None:
            raise ValueError(
                f"Shot {index + 1}: cannot retain authored action and supernatural event "
                "inside the actual model tokenizer context")
        if anomaly not in selected or action not in selected:
            raise RuntimeError("Supernatural visual beat or authored action was dropped")
        prompts.append(selected)
    if len(set(prompts)) != 6:
        raise ValueError("Repeated directed paranormal beat")
    return prompts
