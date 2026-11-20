"""Experimental scene discrimination, not a substitute for visual review."""
import math

MODEL = "openai/clip-vit-base-patch32"

def choose_candidate(candidates):
    """Select the valid candidate with strongest target-vs-other-shot margin.
    No calibrated threshold or claims about anatomy or identity continuity.
    """
    valid = []
    for i, c in enumerate(candidates):
        if c["reasons"]:
            continue
        score, margin, technical = c["semantic_score"], c["semantic_margin"], c["score"]
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (score, margin, technical)):
            raise ValueError("Non-finite semantic result")
        valid.append(((margin, score, technical, -i), i))
    if not valid:
        raise RuntimeError("No technically valid semantic candidate")
    return max(valid)[1]

class SceneRanker:
    def __init__(self, prompts, revision):
        import torch
        from transformers import CLIPModel, CLIPProcessor
        self.torch = torch
        self.processor = CLIPProcessor.from_pretrained(MODEL, revision=revision)
        self.model = CLIPModel.from_pretrained(MODEL, revision=revision).eval()
        self.prompts = list(prompts)
        if len(self.prompts) < 2:
            raise ValueError("Semantic ranking needs competing scenes")
        tokens = self.processor.tokenizer(self.prompts, padding=True, truncation=False, return_tensors="pt")
        if tokens["input_ids"].shape[1] > self.model.config.text_config.max_position_embeddings:
            raise ValueError("Semantic prompt exceeds token limit")
        self.tokens = tokens

    def score(self, image, index):
        # Letterbox so the portrait composition is not silently center-cropped.
        from PIL import ImageOps
        square = ImageOps.pad(image.convert("RGB"), (224, 224), color=(127, 127, 127))
        inputs = self.processor(images=square, return_tensors="pt")
        with self.torch.inference_mode():
            logits = self.model(**self.tokens, **inputs).logits_per_image[0].tolist()
        target = float(logits[index])
        competitors = [float(v) for i, v in enumerate(logits) if i != index]
        if not all(math.isfinite(v) for v in [target, *competitors]):
            raise ValueError("Non-finite CLIP logits")
        return target, target - max(competitors)
