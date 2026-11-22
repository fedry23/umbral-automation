"""Versioned horror direction for PRIVATE SDXL Lightning previews only.

The previous 'photorealistic' prompts depicted everyday objects without
the supernatural beats. Each shot now names a specific impossible visual event,
with progressive dread and camera/light direction. No automatic approval.
Only opt-in UMBRAL_HORROR_DIRECTION=horror-v2 uses these prompts.
"""
import re
from scripts.storyboard import validate_storyboard

VERSION = "horror-v2"

# Exactly one story-specific supernatural image per narration section.
# Deliberately specific: a generic horror adjective is not an image event.
BEATS = {
    # The 28-Nov early story is threatening because the same strip of tape
    # MOVES ON ITS OWN and finally restrains someone; a static normal corridor
    # with yellow tape does not depict the authored supernatural event.
    "La cinta amarilla": (
        "The yellow warning tape has CRAWLED several metres toward the closed office door, its loose end curled upward like a living snake in the deserted corridor",
        "One free end of the yellow tape STRETCHES BY ITSELF toward the janitor's hand as the other end is pressed onto the cracked floor tile",
        "The long strip of yellow tape SLITHERS ACROSS THE TILES LIKE A LIVING SNAKE, its leading edge lifted from the floor, with impossible black shadows",
        "The yellow floor tape CRAWLS INTO THE DARK STOREROOM ALONE, curling across the threshold while nobody touches it",
        "Living yellow tape WRIGGLES THROUGH THE NARROW GAP under the tightly CLOSED office door, creeping inward toward its unseen victim",
        "Yellow floor tape WRAPS ITSELF TIGHT around a terrified worker's black shoes and ankles, pulling like a constricting serpent, impossible supernatural movement",
    ),
    "La pintura fresca": (
        "A human palm pushes out from BEHIND the perfectly smooth wet plaster",
        "Five long inward gouges emerge by themselves as the scraper lifts",
        "A human silhouette silently bulges behind the wall where nobody stands",
        "The five grooves reappear under fresh wet paint without a hand touching them",
        "A full forearm presses out of the solid wall, stretching the paint skin",
        "A human shoulder silently protrudes downward from the solid ceiling above him",
    ),
    "El último doblaje": (
        "The magnetic tape turns although the studio is deserted, one unlit corner watches",
        "He drinks desperately while his own shadow stays motionless near the recorder",
        "The left hand is rigid and pale while the other hand still moves",
        "The right hand reaches STOP as the machine's moving reels cast impossible shadows",
        "A small blade slips toward the tape while an unseen finger presses PLAY",
        "He is unnaturally rigid in his chair while the two reels spin endlessly",
    ),
    "El ascensor de servicio": (
        "The ID photo subtly shows him decades younger than the worker holding it",
        "The empty office landing has an unnaturally deep dark end beyond the elevator",
        "A wedding ring-shaped pale mark remains, the ring itself has vanished",
        "Elevator floor is misaligned with the landing and the emergency exit is bricked shut",
        "His phone has no signal, and his reflection looks like a much younger stranger",
        "Handrail towers above a suddenly child-height viewpoint, the basement button lights alone",
    ),
    "El banco de la parada": (
        "A puddle forms UNDER the dry green bench in a deserted midnight bus shelter",
        "The puddle reflects the very same bus shelter completely submerged underwater",
        "Water rises over the shoes despite the surrounding asphalt being bone dry",
        "Wet footprints lead away from the bench while the dry street remains empty",
        "Ghostly trapped passengers press both palms against the windows of a passing night bus",
        "The puddle reflects a man STILL SITTING on the bench although it is empty above",
    ),
    "El carrete sin revelar": (
        "The instant photo shows this room from inside a dark closed wardrobe",
        "A broken white mug appears in an unexplained instant photo before the man notices",
        "The camera points at the sofa but the developed photo shows a view FROM beneath it",
        "A low predatory point of view peers from the blackness under the sofa",
        "The camera ejects a fresh photograph despite being switched off inside its box",
        "The developing photograph shows two human teeth framing a room from INSIDE a mouth",
    ),
    "El paquete sin remitente": (
        "The open cardboard box contains the EXACT striped doormat that is missing upstairs",
        "The table lamp rests inside an impossibly small box, its power cord severed",
        "The spoon and bathroom mirror appear impossibly within the same small box",
        "The stone propping the cardboard lid slips while no hand touches it",
        "The apartment door has a perfectly smooth area where the door lock should be",
        "Blue pajama cloth is trapped inside the closed cardboard box, as if a person were being taken",
    ),
    "El grifo del patio": (
        "Water droplets flow UPWARD into the dry tap, defying gravity in still air",
        "A wet chalk-white outline marks where water vanished from the blue bucket",
        "The dog bowl is completely dry while wet rings remain around it",
        "The sleeping old man holds a glass whose water level falls by itself",
        "The brass tap threads twist free and blackness seems to inhale from the open pipe",
        "His hands are paper-thin and translucent like dried parchment",
    ),
    "La última página": (
        "A black notebook predicts an incident before it happens, untouched beside a dark window",
        "A museum display case shatters outward with NO person anywhere near it",
        "An emergency doorway swings open into a depthless pitch-black corridor",
        "Fresh handwriting appears on torn pages although the pen lies untouched",
        "The guard faces smooth uninterrupted stone where a museum exit was seconds ago",
        "Only the black notebook remains on the desk; a shadow stands beyond an empty window",
    ),
    "El plano del desván": (
        "The floor plan contains an impossible extra room drawn exactly over the bed",
        "A tape measure crosses a bed while an extra doorway is faintly outlined behind it",
        "A doorway has vanished, leaving perfectly seamless plaster and an abandoned frame shadow",
        "A pencil draws a new door and the same door appears in the shadow behind the paper",
        "A second line draws itself on the plan while the paper lies untouched",
        "Multiple narrow doors surround the SAME bed, all leading into impossible darkness",
    ),
    "El taxi de la otra acera": (
        "The red taximeter counts upward while the taxi remains absolutely stationary",
        "The driver grips the wheel but his reflection is missing from the windscreen",
        "Streetlights outside the still taxi recede into an impossible vanishing point",
        "A passenger reaches for the meter as the surrounding city stretches away unnaturally",
        "The taxi door opens at the exact apartment doorway with no street in between",
        "The apartment entrance opens directly into the rear seat of the SAME black taxi",
    ),
    "El botón verde": (
        "A mechanical time clock prints an impossible FUTURE exit time on a cardboard card",
        "The worker stares at a card showing the exact minute he will disappear",
        "An empty work uniform collapses beside the open locker, its wearer vanished",
        "A clock card bears a second time before the worker has even arrived",
        "The locked turnstile traps the worker while a shadow waits beyond it",
        "A second card bearing the SAME name slides out on its own from the machine",
    ),
    "La radio del sótano": (
        "An unplugged old radio crackles in the damp basement, its dial moving",
        "Disconnected batteries sit beside the radio although its signal still glows",
        "The tuning knob turns and fresh scrape marks appear inside the closed basement door",
        "The elderly woman stares toward her wardrobe as something knocks from INSIDE it",
        "The dial moves backwards as the shadow under the basement door retreats",
        "The old woman clutches her chest as an unseen knock sounds from within her ribs",
    ),
    "Las huellas de sal": (
        "Pale WHITE SALT crystals form small child-sized footprints on clean kitchen tiles",
        "A broom erases pale salt footprints that reappear behind the broom",
        "A child's shoes match the fresh salt footprints before the door is opened",
        "Two gigantic SALT footprints materialize on the locked door's INSIDE",
        "Enormous pale salt footprints form behind the man while nobody is there",
        "Overlapping pale WHITE SALT footprints surround his feet, some beginning inside his own prints",
    ),
    "El abrigo de la consigna": (
        "The torn-seam charcoal overcoat hangs alone in a deserted cinema cloakroom",
        "An impossible cinema ticket bearing tomorrow's date emerges from the coat",
        "A receipt and a shopping bag lie next to the same torn charcoal coat, no owner visible",
        "A small brass key appears in a coat pocket that was empty moments ago",
        "The folded note carries his own apartment number, an unseen figure waits by the door",
        "He holds the key while a second shadow wearing his coat stands behind the closed door",
    ),
}

COMMON = "Photoreal psychological horror film still"
STYLES = (
    "Uncanny calm, cold side lighting, deep shadow at frame edge, uneasy empty space",
    "Tense off-centre framing, one harsh practical lamp, long unnatural shadows",
    "Claustrophobic framing, sharply lit anomaly, darkness swallowing the background",
)
SHORT_STYLE = "Low-key cinematic lighting, oppressive shadows, realistic texture"
MIN_STYLE = "Cinematic dread, single light, shadows"

def _clean(text):
    text = re.sub(r",?\s*cinematic realistic horror,?\s*vertical frame,?\s*no text\.?$", "", text, flags=re.I)
    return text.strip(" ,.")

def _fits(prompt, tokenizer):
    return len(tokenizer(prompt, truncation=False).input_ids) <= tokenizer.model_max_length

def directed_prompts(story, tokenizer):
    shots = validate_storyboard(story)
    beats = BEATS.get(story.get("title"))
    if beats is None or len(beats) != len(shots) or len(beats) != 6:
        raise ValueError("No curated horror beats for this editorial story")
    prompts = []
    for i, (shot, beat) in enumerate(zip(shots, beats)):
        # Preserve the authored photographed action rather than drifting into
        # an unrelated generic haunted scene. Fall back to shorter action only
        # if the model's actual tokenizer requires it; NEVER truncate the beat.
        for base in (_clean(shot["prompt"]), _clean(shot["action"])):
            for style in (STYLES[min(i//2, 2)], SHORT_STYLE, MIN_STYLE):
                prompt = f"{COMMON}. {base}. {beat}. {style}. No words, no watermark"
                if _fits(prompt, tokenizer):
                    prompts.append(prompt)
                    break
            if len(prompts) == i+1:
                break
        if len(prompts) != i+1:
            raise ValueError(f"Horror shot {i+1} exceeds actual tokenizer context")
    if len(set(prompts)) != 6:
        raise ValueError("Repeated horror direction")
    return prompts
