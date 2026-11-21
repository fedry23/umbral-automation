"""Targeted private horror-v3 experiment for the rejected 22-Nov bus-stop Reel.

Scenes are composed as *observable events*, not an atmospheric adjective.
The impossible reflection is difficult for diffusion: this is a review candidate
and NEVER evidence of approval. Its own revision is stored separately.
"""
from scripts.storyboard import validate_storyboard

VERSION = "horror-v3"
TITLE = "El banco de la parada"
PROMPTS = (
    "Photoreal cinematic horror, vertical frame. EMPTY green metal bus stop at NIGHT. "
    "A single bench stands under a flickering lamp. An unnatural black puddle forms directly beneath the bench. "
    "Cold rain fog, strong dark shadows, unsettling quiet, no text.",
    "Photoreal cinematic horror, vertical frame. Close low angle of a deep black puddle directly UNDER a green bus stop bench AT NIGHT. "
    "Inside the WATER REFLECTION, the bus shelter is fully FLOODED, water touching its roof. "
    "Above the water surface the same shelter remains dry. Cold moonlight, no text.",
    "Photoreal cinematic horror, vertical frame. CLOSEUP of a terrified person's TWO SHOES and trouser legs, "
    "half SUBMERGED in water rising from the black puddle at the bus stop. "
    "The surrounding road is DRY, dark empty asphalt. Midnight light, no boats, no text.",
    "Photoreal cinematic horror, vertical frame. LOW ANGLE of clearly visible wet HUMAN SHOE FOOTPRINTS "
    "leading AWAY from a GREEN BUS STOP BENCH across otherwise dry black asphalt at NIGHT. "
    "No people in the frame. Long cold shadows, unnerving emptiness, no text.",
    "Photoreal cinematic horror, vertical frame. CLOSEUP of the SIDE WINDOWS of a moving NIGHT BUS under a single streetlight. "
    "TERRIFIED TRAPPED PASSENGERS INSIDE the bus press their OPEN PALMS flat against the glass and scream silently. "
    "Wet misted windows, harsh blue light, no text.",
    "Photoreal cinematic supernatural horror, vertical frame. At NIGHT a GREEN BUS STOP BENCH is EMPTY in the real world. "
    "The camera looks DOWN into the black puddle directly below it. "
    "ONLY IN THE WATER REFLECTION appears a lone MAN SITTING on the bench. "
    "Impossible reflection, clearly empty bench above, cold light, no text.",
)

def _new_story_prompts(shots, tokenizer):
    """V3 film language for unseen authored episodes, not automatic approval.

    Prioritizes the *visible physical action* and a stable authored location.
    We must not invent story-specific supernatural events or drop the action
    at CLIP's actual tokenizer limit.
    """
    prompts=[]
    for i, shot in enumerate(shots):
        action=shot["action"].strip(" .")
        original=shot["prompt"].split(". ")
        setting=original[1].strip(" .") if len(original)>1 else ""
        if not action or len(action)>400:
            raise ValueError("Invalid authored physical horror action")
        light=("eerie empty space, cold teal shadows, one dim amber practical light"
               if i<2 else "deep supernatural dread, hard teal-green sidelight, heavy dark shadows")
        candidates=(
            f"Photoreal cinematic psychological horror, portrait. {action}. {setting}. {light}. No text",
            f"Photoreal cinematic horror, portrait. {action}. {setting}. dark shadows, eerie atmosphere. No text",
            f"Photoreal cinematic horror, portrait. {action}. ominous shadows. No text",
        )
        prompt=next((p for p in candidates if len(tokenizer(p,truncation=False).input_ids)<=tokenizer.model_max_length),None)
        if prompt is None:
            raise ValueError(f"Horror v3 scene {i+1} exceeds actual tokenizer context")
        prompts.append(prompt)
    return prompts


def directed_prompts_v3(story, tokenizer):
    shots=validate_storyboard(story)
    if len(shots)!=6:
        raise ValueError("Storyboard scene count changed")
    if story.get("title")==TITLE:
        prompts=list(PROMPTS)
    else:
        prompts=_new_story_prompts(shots,tokenizer)
    for i,prompt in enumerate(prompts):
        if len(tokenizer(prompt,truncation=False).input_ids)>tokenizer.model_max_length:
            raise ValueError(f"Horror v3 scene {i+1} exceeds actual tokenizer context")
    if len(set(prompts))!=6:
        raise ValueError("Repeated visual beats")
    return prompts
