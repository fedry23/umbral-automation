"""Run pinned public CLIP image/text inference without HF OIDC or Meta secrets.

The parent passes six private ephemeral frames and storyboard prompts by private
filesystem. Do not print, save or upload images or narration in Actions logs.
"""
import argparse
import json
from pathlib import Path

MODEL="openai/clip-vit-base-patch32"
REVISION="d15b5f29721ca72dac15f8526b284be910de18be"


def run(folder):
    import torch
    from PIL import Image
    from transformers import CLIPModel, CLIPProcessor
    folder=Path(folder)
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("Unsafe CLIP inference directory")
    prompts=json.loads((folder/"prompts.json").read_text(encoding="utf-8"))
    if not isinstance(prompts,list) or len(prompts)!=9 or any(not isinstance(p,str) or not 15<=len(p)<=650 for p in prompts):
        raise RuntimeError("Invalid nine authored/negative visual prompts")
    images=[]
    for i in range(6):
        file=folder/f"scene_{i:02}.png"
        if file.is_symlink() or file.stat().st_size>25_000_000:
            raise ValueError("Unsafe visual input")
        with Image.open(file) as im:
            if im.format!="PNG" or im.size!=(512,896):
                raise ValueError("Wrong frame for semantic inference")
            im.load()
            images.append(im.convert("RGB"))
    torch.set_num_threads(4)
    processor=CLIPProcessor.from_pretrained(MODEL,revision=REVISION)
    model=CLIPModel.from_pretrained(MODEL,revision=REVISION,use_safetensors=True)
    model.eval()
    tensors=processor(images=images,text=prompts,return_tensors="pt",
                      padding=True,truncation=True)
    with torch.inference_mode():
        logits=model(**tensors).logits_per_image.float().cpu().tolist()
    if len(logits)!=6 or any(len(row)!=9 for row in logits):
        raise RuntimeError("Missing neural image/text outputs")
    (folder/"clip_scores.json").write_text(json.dumps(logits),encoding="utf-8")
    print("UMBRAL3_CLIP_FRAMES_SCORED=6 model=pinned public ViT-B/32")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--folder",type=Path,required=True)
    args=p.parse_args()
    run(args.folder)
