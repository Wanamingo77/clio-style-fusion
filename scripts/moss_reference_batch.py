"""Render the reference image of Moss Image styles (Film / Camera) through a running ComfyUI.

Same recipe as the rest of the gallery: ONE subject prompt, ONE seed (1997, the manifest's), so the only
variable is the style. The style goes through the ClioStyle node (same template as the real node), its
negative prompt (MOSS base + the style's own) goes to the negative encode. Output is a 512px JPEG at the
path the gallery expects (gallery/moss/thumbs/<style>.jpg), exactly like the existing thumbs.

Needs a python with PIL (ComfyUI's embedded python works) and a running ComfyUI with this node installed.
Idempotent: styles that already have an image are skipped (use --force to redo, --styles to pick some)."""
import argparse
import io
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comfy_gen import SERVER, post_prompt, wait_for, collect_images
from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SUBJECT = ("a playful young woman with long pink hair in a ponytail and gold eyes, wearing a loose, baggy "
           "white shirt slipping off a shoulder, sparkle manicure, smug knowing grin, standing in a low-lit "
           "cute bedroom, mid shot, looking at viewer")
TEMPLATE = "Style: {name}: {style}. Subject: {prompt}"


def safe_name(name):
    return "".join(c for c in name if c.isalnum() or c in " -_()").strip()


def moss_workflow(style, seed, prefix, w=1024, h=1024, steps=25, cfg=2.5, shift=5,
                  unet="moss_image_sft_int8_convrot.safetensors",
                  clip="qwen3.5_9b_ultra_uncensored_heretic_int8_convrot.safetensors",
                  vae="flux2-vae.safetensors", sampler="er_sde", scheduler="linear_quadratic"):
    # defaults mirror the user's working MOSS workflow (MOSS_video_replica)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": unet, "weight_dtype": "default"}},
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": shift}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": clip, "type": "moss_image", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": vae}},
        "5": {"class_type": "ClioStyle", "inputs": {"prompt": SUBJECT, "style": style, "template": TEMPLATE}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ["5", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": ["5", 1]}},
        "8": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "9": {"class_type": "KSampler",
              "inputs": {"model": ["2", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["8", 0],
                         "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler,
                         "scheduler": scheduler, "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["4", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": prefix}},
    }


def fetch_image(info):
    q = urllib.parse.urlencode({"filename": info["filename"], "subfolder": info.get("subfolder", ""),
                                "type": info.get("type", "output")})
    with urllib.request.urlopen(f"{SERVER}/view?{q}") as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser(description="Render reference images for the Film/Camera (Moss) styles")
    ap.add_argument("--styles", nargs="*", default=None, help="style names (default: every Film/Camera style)")
    ap.add_argument("--seed", type=int, default=1997)
    ap.add_argument("--force", action="store_true", help="re-render even if an image exists")
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--cfg", type=float, default=2.5)
    args = ap.parse_args()

    with open(os.path.join(ROOT, "styles.json"), encoding="utf-8") as f:
        entries = json.load(f)
    names = args.styles or [e["name"] for e in entries if e.get("section") in ("Film", "Camera")]
    out_dir = os.path.join(ROOT, "gallery", "moss", "thumbs")
    os.makedirs(out_dir, exist_ok=True)

    todo = [n for n in names if args.force or not os.path.isfile(os.path.join(out_dir, safe_name(n) + ".jpg"))]
    print(f"{len(names)} styles, {len(names) - len(todo)} already done, {len(todo)} to render")
    for i, name in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {name} ...", flush=True)
        graph = moss_workflow(name, args.seed, "clio_moss_ref/" + safe_name(name), steps=args.steps, cfg=args.cfg)
        entry = wait_for(post_prompt(graph)["prompt_id"], timeout=1800)
        imgs = collect_images(entry)
        if not imgs:
            print("  !! no image returned, skipping")
            continue
        im = Image.open(io.BytesIO(fetch_image(imgs[0]))).convert("RGB")
        im.thumbnail((512, 512), Image.LANCZOS)
        im.save(os.path.join(out_dir, safe_name(name) + ".jpg"), quality=85)
        print("  ->", safe_name(name) + ".jpg", im.size, flush=True)
    print("done")


if __name__ == "__main__":
    main()
