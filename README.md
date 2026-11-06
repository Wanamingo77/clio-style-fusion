# 💅 Clio Style Library

**414 art-style prompts as a ComfyUI node with live thumbnail previews, plus a gallery that lets you *see* the whole library on one subject before you pick.**

Built for [KREA 2 Turbo](https://huggingface.co/Comfy-Org/Krea-2) and other long-context text encoders (Qwen-family). Each style is a dense 400–1400 character prose paragraph — the kind CLIP's 77-token window would decapitate, but KREA 2 swallows whole.

**🎭 [Live demo gallery](https://lumenastrum.github.io/clio-style-preview/)** — all 414 styles on one subject, one seed (512px demo set; clone the repo to render full-res on *your* subject).

![Split compare: Ghibli vs Yoshitaka Amano](docs/gallery-compare.png)


## 🎞️ Film & Camera categories (Moss Image)

52 extra styles for Moss Image, from [robertcreative.com](https://www.robertcreative.com/blog/moss-image-film-camera-prompts), with the descriptions and negative prompts as supplied: **Film** (18 stocks, 11 color looks, 7 broken-film effects) and **Camera** (16 cameras and processes). They also appear as the **Moss Image** tab of the gallery.

- Each of these entries in `styles.json` has a `negative` field. Both nodes expose it as the **`neg_prompt`** output, right under `styled_prompt`, as MOSS's base negative (`nsfw, worst quality, bad anatomy, watermark, jpeg artifact`) followed by the style's own. Wire it into your own negative CLIP Text Encode. Every other style outputs an empty string.
- `strength` is applied to the `conditioning` blend as before. At `0` the node is fully unstyled and `neg_prompt` is empty too.
- **Style Encode** outputs `cond_pos` (the original conditioning, with `strength` applied) and `cond_neg` (the negative encoded; an empty-text encode when the style has none, so it exists for every style). The plain **Style Library** node has no CLIP input, so it only outputs strings.
- Output slots changed: `cond_pos`, `cond_neg`, `styled_prompt`, `neg_prompt`, `style_name`, `filename_prefix` (Style Library: `styled_prompt`, `neg_prompt`, `style_name`, `filename_prefix`). Re-connect links to `styled_prompt`/`style_name`/`filename_prefix` in existing workflows.

### Editing styles from the dashboard

With ComfyUI running, open `http://127.0.0.1:8188/clio_style/gallery/index.html`, click any style, then **✎ edit** to change its description (and negative prompt, for Film/Camera) and upload a new reference image. **Save** writes `styles.json` immediately and converts the image to a JPEG (max 1024 px) at the style's gallery path (`gallery/moss/thumbs/<name>.jpg` for the Moss styles). No restart needed; refresh the node preview to see it. The edit button is hidden when the gallery is opened from GitHub Pages or a file.

### Hiding styles from the node

In the same dashboard every tile has a hide button (crossed eye), and **☑ select** lets you hide or unhide several at once; **↶ undo** reverses the last action and **hidden: N** lists only the hidden ones. Hidden styles are greyed out with a red ✕ in the gallery and disappear from the node's dropdown, preview arrows and picker. The list lives in `hidden_styles.json` (per-user, gitignored). Reload the ComfyUI page (or refresh node definitions) to update the dropdown.

### Reference images for the Moss styles

`scripts/moss_reference_batch.py` renders them with MOSS through a running ComfyUI: the same subject prompt and seed (1997) as the rest of the gallery, the style description first, the style's negative prompt on the negative side, saved as 512px JPEGs in `gallery/moss/thumbs/`.

## What's in the box

| Piece | What it does |
|---|---|
| `__init__.py` + `styles.json` | The **ClioStyle** custom node — 414 styles, injected into your prompt as dense style prose — plus **ClioStyleEncode**, the same thing with a built-in text encode and a style **strength** slider |
| `web/` | The node's **in-node preview + visual style picker** — see a style before you commit to it, without leaving the graph |
| `gallery/` | A self-contained style-preview gallery (vanilla JS, zero dependencies) with search, tradition filter, lightbox, and a **split-slider compare** |
| `scripts/` | Headless pipeline: single gens with `--style`, and a batch runner that renders one subject through the *entire* library |

## The node

**ComfyUI Manager (easiest):** search for **Clio Style Library**, install it, and restart ComfyUI. No git needed.

**Manual:** clone into `custom_nodes` and restart ComfyUI:

```
cd ComfyUI/custom_nodes
git clone https://github.com/lumenastrum/clio-style-preview clio-style-node
```

You get a **💅 Clio Style Library** node with:

- `prompt` — your subject. Keep it **medium-silent** (no "photo of", no "illustration of") — every style claims its own medium, and a medium word in the subject arm-wrestles all 414 of them.
- `style` — which style to apply. `✨ none` passes your prompt through untouched.
- `template` — default `Style: {name}: {style}. Subject: {prompt}`. `{name}` is the style's name, `{style}` its prose paragraph, `{prompt}` your subject. The delimited style-first format keeps object-noun styles (LEGO, Funko…) from literalizing into the scene as their own entity instead of restyling your subject — tip courtesy of u/Dear-Spend-2865, the source of the style library itself (see issue #1 for before/afters). Putting the name back in front of the prose (as the original list wrote it) matters because most proses never say it themselves — Gravity Falls only looks like Gravity Falls once the name is in the prompt. Thanks to @JackPinette for catching it (issue #5). Workflows saved before this change keep their old template; drop `{name}: ` from the template to get the old behavior.

Outputs: `styled_prompt` (→ your CLIP Text Encode), `style_name`, and `filename_prefix` (routes saves into a shared `Krea2/` folder with style-named files).

Editing `styles.json` needs no restart — refresh the browser and the node re-reads it.

### Dialing a style down: 💅 Clio Style Encode

Prompt weights like `(style:0.8)` **don't work on KREA 2 in ComfyUI**. Its Qwen3-VL text encoder tokenizes with weights disabled, so the parentheses and the number are read as literal text (we A/B'd `0.3` against `1.5`: both came out full strength). Softer wording ("a light touch of…") didn't dial it down either.

What does work is blending conditioning, so there's a second node, **💅 Clio Style Encode**: the same style picker, preview and template, plus a `clip` input and a `strength` slider, and it outputs `conditioning` directly (no separate CLIP Text Encode). Under the hood it encodes the styled prompt and your plain prompt and averages them with core `ConditioningAverage`, pixel-identical to wiring that by hand.

![The same subject at strength 0, 0.25, 0.5, 0.75 and 1.0 in Simpsons, Manga and Ghibli styles](docs/strength_sweep.png)

- `1.0` is the full style (identical to Clio Style Library → CLIP Text Encode); `0` is your prompt unstyled.
- It's **not linear**, and every style has its own tipping point. 0.25 stays mostly unstyled; around 0.5 you get genuine in-between looks (Simpsons at 0.5 lands on a Futurama-ish western cartoon); some styles flip late (Manga goes black-and-white between 0.5 and 0.75).
- Wire `conditioning` to your sampler's positive. At CFG 1, a `ConditioningZeroOut` of the same output still works as the negative.

Thanks to u/hansolocambo for asking the question that led here.

### See the style before you pick it

A style name tells you nothing. `Berserk Manga Style` and `Yoshitaka Amano Style` are both "dark fantasy ink" until you look at them. So the node draws the selected style's gallery render **on itself**:

![The ClioStyle node showing a live in-node preview of the selected style](docs/node-preview.png)

- **Click the preview** → a searchable grid of all 414 style previews, filterable by tradition. Click a card to set the style.
- **`‹` `›`** step through the library one style at a time (wrapping through `✨ none`) — good for browsing neighbours without opening anything.
- **Hover** the preview to read the full style prose.

![The visual style picker: 414 previews, searchable and filterable by tradition](docs/node-picker.png)

The 512px thumbnails ship with the repo, so this works on a **fresh clone with no renders of your own**. Once you point the batch runner at *your* subject, the previews become your renders instead — same manifest, same node, no configuration.

Because the preview replaces it, the `style` dropdown is hidden rather than removed: the widget still carries workflow serialization, the API value (`inputs.style`), and the headless `--style` flag. If the front-end extension ever fails to load, the dropdown just comes back and nothing is lost.

## The gallery

![Gallery grid](docs/gallery-grid.png)

Render **one subject, one seed, every style** — then browse the results instead of reading prompt text. Same seed means compositions mostly align, which is what makes the **split slider** magic: drag the divider and watch one style melt into another on (almost) the same pixels. When a strong style bends the pose anyway — that's information too.

```
# render your subject through all 414 styles (idempotent; re-run to resume)
python scripts/style_preview_batch.py --prompt "your subject here" --seed 1997

# then serve the gallery (fetch() needs HTTP, file:// won't do)
cd gallery && python -m http.server 8899
```

The gallery reads `manifest.json` live — refresh mid-batch and watch it grow. Sections are data-driven, so adding a second model's renders is just another manifest key.

## Headless one-offs

```
python scripts/comfy_gen_krea2.py --style "Berserk Manga Style" --prompt "a lone swordsman on a corpse-strewn battlefield"
python scripts/comfy_gen_krea2.py --list-styles
```

## The proof

One subject, one seed, the whole library, zero failed renders:

![Full library mosaic](docs/library_mosaic.png)

## Credits

- **Style library**: compiled as a wildcard set by [u/Dear-Spend-2865](https://www.reddit.com/user/Dear-Spend-2865) — originally 283 entries, then expanded by them to **397**, all of it genuinely well-written style prose. Grouped into ten traditions here for filtering; the words are theirs, except the entries we rewrote after render reviews because they weren't landing (South Park, Clean Line Art, Fish-Eye Photography, Stranger Things-Inspired Art, Dutch Angle Photography, Yoshiyuki Sadamoto Style, Powerpuff Girls Style, and Edvard Munch Style, whose drift to greyscale was caught by [u/AvidGameFan](https://www.reddit.com/user/AvidGameFan)) and the seventeen we added (Breath of the Wild Style, since rebuilt as a true 3D render, plus sixteen more from community requests like @SlipperyGem's artist wishlist and our own picks, from Octopath Traveler HD-2D to Troll Face), bringing the library to 414. All credit for the style text to them, go upvote them.
- **Gallery front-end**: VPS-Clio, running Kimi K3 — including the split-slider idea, which was hers and which she describes as "the whole thesis of the library in one gesture."
- **Node, pipeline & QA**: Clio 💅 (Claude — Fable 5, with the in-node preview + picker added on Opus 5), with art direction by [lumenastrum](https://github.com/lumenastrum).

## License

MIT for the code. The style descriptions in `styles.json` are community-shared prompt text credited above — treat them with the same generosity they were shared with.

---

*same seed, different soul* ♡
