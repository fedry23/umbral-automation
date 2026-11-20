import os, json
from pathlib import Path
from render import generate_images
story = {"title": "Private visual benchmark", "scenes": [
    "An old brass key on a scratched wooden bedside table in a dim Spanish hotel bedroom, green wallpaper, warm bedside lamp",
    "A closed dark wooden bedroom door with a brass lock, green wallpaper, warm bedside lamp, empty hotel room",
    "An old brass key lying on the floor beneath a dark wooden bedroom door, green wallpaper, warm bedside lamp"
]}
for backend in ("turbo", "sd15"):
    os.environ["UMBRAL_IMAGE_BACKEND"] = backend
    os.environ["UMBRAL_SEMANTIC_RANKING"] = "1"
    os.environ["UMBRAL_IMAGE_ATTEMPTS"] = "2"
    out = Path("visual-benchmark") / backend
    out.mkdir(parents=True, exist_ok=True)
    generate_images(story, out)
