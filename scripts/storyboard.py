"""Versioned shot contract. Structural validation is not visual or narrative QA."""
import math
import re

def _text(value, field):
    if not isinstance(value, str) or not value.strip() or value != ' '.join(value.split()):
        raise ValueError(f'Invalid {field}')
    return value

def validate_storyboard(story):
    board = story.get('storyboard')
    if not isinstance(board, dict) or board.get('version') != 1:
        raise ValueError('Unsupported storyboard')
    canon = board.get('continuity')
    if not isinstance(canon, dict) or not canon:
        raise ValueError('Missing continuity bible')
    for ident, description in canon.items():
        if not isinstance(ident, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', ident):
            raise ValueError('Invalid continuity identifier')
        _text(description, 'continuity description')
    shots = board.get('shots')
    if not isinstance(shots, list) or not 3 <= len(shots) <= 8:
        raise ValueError('Expected three to eight shots')
    if len(shots) != len(story.get('scenes', [])):
        raise ValueError('Scene/shot count mismatch')
    used, prompts = set(), set()
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError('Invalid shot')
        for key in ('narration', 'action', 'camera', 'prompt'):
            _text(shot.get(key), key)
        prompt = shot['prompt']
        if not 8 <= len(prompt.split()) <= 50:
            raise ValueError('Prompt must contain 8–50 words before token validation')
        if prompt.casefold() in prompts:
            raise ValueError('Repeated shot prompt')
        prompts.add(prompt.casefold())
        refs = shot.get('references')
        if (not isinstance(refs, list) or not refs
                or any(not isinstance(ref, str) or ref not in canon for ref in refs)
                or len(set(refs)) != len(refs)):
            raise ValueError('Unknown or repeated continuity reference')
        # Require each referenced concise visual anchor literally in the prompt.
        for ref in refs:
            if canon[ref].casefold() not in prompt.casefold():
                raise ValueError(f'Prompt omits continuity anchor: {ref}')
        used.update(refs)
    if set(canon) != used:
        raise ValueError('Unused continuity reference')
    if ' '.join(shot['narration'] for shot in shots) != story.get('narration'):
        raise ValueError('Shot narration must partition the original text exactly')
    return shots

def shot_boundaries(shots, cues, branding):
    """Map a shot to real speech cue boundaries, never interpolate word counts.
    Subtitle positions within a sentence remain estimated by the existing TTS.
    Reject partial cues, missing text and impossible time ranges.
    """
    start, end = float(branding['intro_end']), float(branding['outro_start'])
    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end:
        raise ValueError('Invalid story timing')
    if not cues or not shots:
        raise ValueError('Missing shot cues')
    story_cues = [(float(a), float(b), t) for a, b, t in cues
                  if a >= start - .02 and b <= end + .02 and t.strip()]
    previous = start - .02
    for a, b, _ in story_cues:
        if not math.isfinite(a) or not math.isfinite(b) or not previous <= a < b:
            raise ValueError('Non-monotonic cues')
        previous = b
    pos, boundaries = 0, [start]
    for i, shot in enumerate(shots):
        if pos >= len(story_cues):
            raise ValueError('Missing cue for shot')
        if i:
            boundaries.append(story_cues[pos][0])
        target = shot['narration']
        actual = ''
        while pos < len(story_cues):
            actual = (actual + ' ' + story_cues[pos][2]).strip()
            pos += 1
            if actual == target:
                break
            if not target.startswith(actual + ' '):
                raise ValueError('Shot boundary must coincide with a complete speech cue')
        if actual != target:
            raise ValueError('Incomplete shot narration')
    if pos != len(story_cues):
        raise ValueError('Unassigned story cues')
    boundaries.append(end)
    if any(b <= a for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError('Non-positive shot duration')
    return boundaries
