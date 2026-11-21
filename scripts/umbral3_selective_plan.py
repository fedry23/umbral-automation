"""Owner-requested selective Horror v3.1 repair plan, kept PRIVATE and opt-in.

Scene indices are zero-based. Unselected V3 PNGs must remain byte-for-byte
identical. This is a photographic correction plan, NEVER owner approval.
"""
from scripts.umbral3_reserve_render import load_slot, catalogs

OLD_BACKEND = "sdxl-lightning-2steps-ov-int8-horror-v3"
NEW_BACKEND = "sdxl-lightning-2steps-ov-int8-horror-v3-1-selective"
TITLE_AND_SHOTS = {
    0: ("La pintura fresca", (0, 2, 4, 5)),
    1: ("El último doblaje", (1, 2, 3, 5)),
    2: ("El ascensor de servicio", (0, 2, 3, 5)),
    3: ("El banco de la parada", (1, 2, 4, 5)),
    4: ("El carrete sin revelar", (0, 2, 5)),
    5: ("El paquete sin remitente", (0, 1, 2, 4, 5)),
    6: ("El grifo del patio", (0, 1, 3, 4, 5)),
    7: ("La última página", (1, 2, 3, 4, 5)),
    8: ("El plano del desván", (0, 2, 3, 4, 5)),
    9: ("El taxi de la otra acera", (0, 2, 4, 5)),
    10: ("El botón verde", (0, 1, 2, 4, 5)),
    11: ("La radio del sótano", (1, 2, 3, 4, 5)),
    12: ("Las huellas de sal", (0, 1, 2, 3, 4, 5)),
    13: ("El abrigo de la consigna", (1, 3, 4, 5)),
}
# First build a mixed 14-story board. Do not generate the remaining seven until
# the owner reviews the corrected high-priority storytelling.
PRIORITY = (0, 2, 5, 8, 10, 11, 12)


def selection(index, anchor, editorial=None):
    if type(index) is not int or index not in TITLE_AND_SHOTS:
        raise ValueError("Unknown selective repair slot")
    story, day, slot = load_slot(index, anchor, editorial or catalogs())
    title, indices = TITLE_AND_SHOTS[index]
    if story["title"] != title:
        raise ValueError("Editorial story changed; human re-review required")
    if (not isinstance(indices, tuple)
            or not indices or len(set(indices)) != len(indices)
            or any(type(i) is not int or not 0 <= i < 6 for i in indices)):
        raise ValueError("Invalid selective scene plan")
    return story, day, slot, indices


def backend_for(index, *, priority_only=True):
    if type(index) is not int or index not in TITLE_AND_SHOTS:
        raise ValueError("Unknown selective repair slot")
    if priority_only and index not in PRIORITY:
        return OLD_BACKEND
    return NEW_BACKEND
