"""💅 Clio Style Library — prompt style injector for KREA 2 / Qwen-encoder models.
Styles live in styles.json beside this file (448 entries: the style library by u/Dear-Spend-2865 plus our own additions,
including the Film and Camera categories adapted for Moss Image, which also carry a negative prompt).
Edit styles.json + refresh the browser to pick up changes — no server restart needed
(INPUT_TYPES re-reads the file on every /object_info fetch).
"""
import json
import os
import re

_DIR = os.path.dirname(os.path.abspath(__file__))
_STYLES_PATH = os.path.join(_DIR, "styles.json")
_NONE = "✨ none"


def _load_entries():
    try:
        with open(_STYLES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_styles():
    return {e["name"]: e["prompt"] for e in _load_entries()}


# Styles hidden from the node (dashboard: gallery/index.html). Per-user preference, kept apart
# from styles.json in hidden_styles.json (a JSON list of names, gitignored).
_HIDDEN_PATH = os.path.join(_DIR, "hidden_styles.json")


def _load_hidden():
    try:
        with open(_HIDDEN_PATH, "r", encoding="utf-8") as f:
            return [n for n in json.load(f) if isinstance(n, str)]
    except Exception:
        return []


# MOSS Image's base negative; prepended to every style that defines its own "negative"
_BASE_NEGATIVE = "nsfw, worst quality, bad anatomy, watermark, jpeg artifact"


def _load_negatives():
    # only styles that define a "negative" (Film / Camera) appear here; the rest output ""
    return {e["name"]: f"{_BASE_NEGATIVE}, {e['negative']}" for e in _load_entries() if e.get("negative")}


def _display_name(style):
    # "Film Noir (2)" is a dedupe suffix for the dropdown, not part of the style's name
    return re.sub(r"\s*\(\d+\)$", "", style)


class ClioStyle:
    @classmethod
    def INPUT_TYPES(cls):
        # library order, not alphabetical — the paste groups styles by tradition
        hidden = set(_load_hidden())
        names = [_NONE] + [n for n in _load_styles() if n not in hidden]
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": "", "dynamicPrompts": False}),
                "style": (names, {"default": _NONE}),
                # Style-first delimited format keeps the style from literalizing into the
                # scene as its own entity (tip from u/Dear-Spend-2865, see repo issue #1).
                # {name} restores the style's name ahead of its prose, as the source list
                # wrote it — many proses never say it themselves (repo issue #5)
                "template": ("STRING", {"default": "Style: {name}: {style}. Subject: {prompt}"}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("styled_prompt", "neg_prompt", "style_name", "filename_prefix")
    FUNCTION = "apply"
    CATEGORY = "Clio 💅"
    DESCRIPTION = "Injects a style paragraph from the 448-entry library into your prompt. " \
                  "Outputs the styled prompt, a negative prompt (Film/Camera styles only, else empty), " \
                  "the bare style name, and a Krea2/<style> filename prefix."

    def apply(self, prompt, style, template):
        prompt = prompt.strip()
        text = _load_styles().get(style, "")
        if style == _NONE or not text:
            styled, name = prompt, "unstyled"
        elif not prompt:
            styled = f"{_display_name(style)}: {text}" if "{name}" in template else text
            name = style
        else:
            # fill the style slots before the prompt, so braces in a user's prompt stay literal
            styled = (template.replace("{name}", _display_name(style)).replace("{style}", text)
                      .replace("{prompt}", prompt).strip())
            name = style
        safe = "".join(c for c in name if c.isalnum() or c in " -_()").strip()
        neg = _load_negatives().get(style, "") if style != _NONE else ""
        return (styled, neg, name, "Krea2/" + safe)


class ClioStyleEncode:
    """ClioStyle + CLIP Text Encode in one node, with a style STRENGTH slider.

    Prompt weights like (text:0.8) do nothing on KREA 2 in ComfyUI: its Qwen3-VL text encoder
    tokenizes with weights disabled, so the parens and number are read as literal text. Softer
    wording ("a light touch of ...") didn't weaken the styles either. What does work is
    blending conditioning: encode the styled prompt and your plain prompt, then average them
    (core ConditioningAverage). A/B on seed 1997 (Simpsons/Manga/Ghibli): 0.5 gives a genuine
    in-between style, 0.25 is mostly unstyled, 0.75 is mostly styled. This node runs the core
    nodes themselves, so it matches that hand-built graph exactly."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                **ClioStyle.INPUT_TYPES()["required"],
                "strength": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "1.0 = full style, 0 = your prompt unstyled. Not linear: around 0.5 "
                               "blends the two looks, 0.25 is mostly unstyled, 0.75 mostly styled.",
                }),
            }
        }

    RETURN_TYPES = ("CONDITIONING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("conditioning", "styled_prompt", "neg_prompt", "style_name", "filename_prefix")
    FUNCTION = "encode"
    CATEGORY = "Clio 💅"
    DESCRIPTION = "Clio Style Library + text encode, with a style strength slider (a conditioning " \
                  "blend between the styled prompt and your plain prompt; prompt weights don't work on KREA 2)."

    def encode(self, clip, prompt, style, template, strength):
        import nodes  # lazy, so scripts can import this file without a running ComfyUI

        styled, neg, name, prefix = ClioStyle().apply(prompt, style, template)
        plain = prompt.strip()
        encode = nodes.CLIPTextEncode().encode
        if strength <= 0.0:
            cond = encode(clip, plain)[0]  # a clean unstyled encode, not a zero-padded blend
            neg = ""  # strength 0 = fully unstyled, so the style's negative goes with it
        else:
            cond = encode(clip, styled)[0]
            if strength < 1.0 and styled != plain:
                cond = nodes.ConditioningAverage().addWeighted(cond, encode(clip, plain)[0], strength)[0]
        return (cond, styled, neg, name, prefix)


NODE_CLASS_MAPPINGS = {"ClioStyle": ClioStyle, "ClioStyleEncode": ClioStyleEncode}
NODE_DISPLAY_NAME_MAPPINGS = {"ClioStyle": "💅 Clio Style Library", "ClioStyleEncode": "💅 Clio Style Encode"}
WEB_DIRECTORY = "./web"


# ---- in-node preview plumbing -----------------------------------------------
# Serves the gallery's own thumbs + manifest through ComfyUI so the front-end
# extension (web/clio_preview.js) can draw a live style preview on the node.
# No image copies, no extra deps — the same files the web gallery already ships.
try:
    from server import PromptServer
    from aiohttp import web as _web

    _GALLERY = os.path.join(_DIR, "gallery")

    def _manifest_entry(style):
        try:
            with open(os.path.join(_GALLERY, "manifest.json"), "r", encoding="utf-8") as f:
                man = json.load(f)
        except Exception:
            return None
        for sec in (man.get("sections") or {}).values():
            for img in sec.get("images", []):
                if img.get("style") == style:
                    return img
        return None

    def _dropin_thumb(style):
        # Reference images for styles with no manifest entry (Film / Camera): drop
        # gallery/moss/thumbs/<style name>.jpg (or .png/.webp) and it shows up in the
        # node preview and the picker — no manifest edit needed.
        safe = "".join(c for c in style if c.isalnum() or c in " -_()").strip()
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            rel = "moss/thumbs/" + safe + ext
            if safe and os.path.isfile(os.path.join(_GALLERY, rel)):
                return rel
        return ""

    @PromptServer.instance.routes.get("/clio_style/thumb")
    async def _clio_style_thumb(request):
        # style names can contain characters filenames can't (colons) — resolve
        # through the manifest instead of guessing a filename
        style = request.rel_url.query.get("style", "")
        entry = _manifest_entry(style)
        rel = (entry.get("thumb") or entry.get("file") or "") if entry else _dropin_thumb(style)
        if not rel:
            return _web.Response(status=404)
        path = os.path.normpath(os.path.join(_GALLERY, rel))
        if not path.startswith(os.path.normpath(_GALLERY) + os.sep) or not os.path.isfile(path):
            return _web.Response(status=404)
        # no-cache: images can be replaced from the dashboard
        return _web.FileResponse(path, headers={"Cache-Control": "no-cache"})

    @PromptServer.instance.routes.get("/clio_style/prose")
    async def _clio_style_prose(request):
        style = request.rel_url.query.get("style", "")
        return _web.json_response({"style": style, "prose": _load_styles().get(style, "")})

    # the gallery's repo-layout fallback fetch ("../styles.json") lands here
    @PromptServer.instance.routes.get("/clio_style/styles.json")
    async def _clio_style_styles(request):
        return _web.FileResponse(_STYLES_PATH)

    # ---- dashboard editing (gallery/index.html) --------------------------------
    # Save a style's description / negative prompt, and replace its reference image.
    # Local-only convenience: ComfyUI serves these on your own machine.
    def _dump_styles(entries):
        # same layout as the checked-in file (CRLF, 1-space list items), so saves diff cleanly
        parts = []
        for e in entries:
            lines = [json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False) for k, v in e.items()]
            parts.append(" {\r\n  " + ",\r\n  ".join(lines) + "\r\n }")
        return "[\r\n" + ",\r\n".join(parts) + "\r\n]"

    def _write_atomic(path, data):
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)

    @PromptServer.instance.routes.post("/clio_style/style")
    async def _clio_style_save(request):
        try:
            body = await request.json()
        except Exception:
            return _web.json_response({"error": "invalid JSON"}, status=400)
        name = body.get("name")
        entries = _load_entries()
        entry = next((e for e in entries if e.get("name") == name), None)
        if entry is None:
            return _web.json_response({"error": "unknown style"}, status=404)
        if "prompt" in body:
            prompt = str(body["prompt"]).strip()
            if not prompt:
                return _web.json_response({"error": "description can't be empty"}, status=400)
            entry["prompt"] = prompt
        if "negative" in body:
            neg = str(body["negative"]).strip()
            if neg:
                entry["negative"] = neg
            else:
                entry.pop("negative", None)
        _write_atomic(_STYLES_PATH, _dump_styles(entries).encode("utf-8"))
        return _web.json_response({"ok": True, "name": name, "prompt": entry["prompt"],
                                   "negative": entry.get("negative", "")})

    @PromptServer.instance.routes.get("/clio_style/style")
    async def _clio_style_get(request):
        name = request.rel_url.query.get("name", "")
        entry = next((e for e in _load_entries() if e.get("name") == name), None)
        if entry is None:
            return _web.json_response({"error": "unknown style"}, status=404)
        return _web.json_response({"name": name, "prompt": entry["prompt"],
                                   "negative": entry.get("negative", ""),
                                   "base_negative": _BASE_NEGATIVE if entry.get("negative") else "",
                                   "section": entry.get("section", "")})

    @PromptServer.instance.routes.get("/clio_style/hidden")
    async def _clio_style_hidden_get(request):
        return _web.json_response({"hidden": _load_hidden()})

    @PromptServer.instance.routes.post("/clio_style/hidden")
    async def _clio_style_hidden_set(request):
        try:
            body = await request.json()
        except Exception:
            return _web.json_response({"error": "invalid JSON"}, status=400)
        known = _load_styles()
        hide = [n for n in (body.get("hide") or []) if n in known]
        show = set(body.get("show") or [])
        # keep library order so the file reads sensibly and diffs are stable
        current = set(_load_hidden()) | set(hide)
        current -= show
        ordered = [n for n in known if n in current]
        _write_atomic(_HIDDEN_PATH, json.dumps(ordered, indent=1, ensure_ascii=False).encode("utf-8"))
        return _web.json_response({"ok": True, "hidden": ordered})

    @PromptServer.instance.routes.post("/clio_style/image")
    async def _clio_style_image(request):
        style = request.rel_url.query.get("style", "")
        if style not in _load_styles():
            return _web.json_response({"error": "unknown style"}, status=404)
        data = await request.read()
        if not data or len(data) > 25 * 1024 * 1024:
            return _web.json_response({"error": "empty or too large (max 25 MB)"}, status=400)
        entry = _manifest_entry(style)
        rel = (entry.get("thumb") or entry.get("file")) if entry else None
        if not rel:
            safe = "".join(c for c in style if c.isalnum() or c in " -_()").strip()
            rel = "moss/thumbs/" + safe + ".jpg"
        path = os.path.normpath(os.path.join(_GALLERY, rel))
        if not path.startswith(os.path.normpath(_GALLERY) + os.sep):
            return _web.json_response({"error": "bad path"}, status=400)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            im.load()
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            im.thumbnail((1024, 1024))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=90)
            data = buf.getvalue()
        except Exception as ex:
            return _web.json_response({"error": f"not a readable image ({ex})"}, status=400)
        _write_atomic(path, data)
        return _web.json_response({"ok": True, "style": style, "file": rel})

    # the whole web gallery, served by ComfyUI itself — the node preview links to it
    # index.html must never be served from the browser cache, or an updated dashboard
    # (e.g. the edit button) keeps showing the old page until a hard refresh
    @PromptServer.instance.routes.get("/clio_style/gallery/index.html")
    async def _clio_style_gallery_index(request):
        return _web.FileResponse(os.path.join(_GALLERY, "index.html"),
                                 headers={"Cache-Control": "no-cache"})

    PromptServer.instance.routes.static("/clio_style/gallery", _GALLERY)
except Exception:
    # headless import (scripts, tests) — no server, no preview, node still works
    pass
