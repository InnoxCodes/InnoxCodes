#!/usr/bin/env python3
"""
Turn a photo into the self-typing ASCII portrait (assets/portrait.svg).

    python3 scripts/make_portrait.py <photo> [--trim-shadow right|left]
    python3 scripts/make_portrait.py <drawing> --illustration

--illustration is for a drawing on a flat, plain background: the background
is flood-filled away from the borders by colour (no Vision, runs anywhere),
the whole image is used as the frame, and the dark outlines are thickened a
little first so thin eye, brow and mouth lines still register as gaps at
character resolution.

It's a "positive" render: light ink on the dark terminal, so the lit face is
the bright part and dark hair and clothes fall away into the background,
like a low-key portrait. Steps:

  1. scripts/cutout.swift finds the person and the face with macOS Vision
     (so this only runs on a Mac; the daily workflow never touches it).
     --trim-shadow cuts a wall shadow off one side by mirroring the clean
     side's outline across the face, which works for straight-on photos.
  2. crop a square around the head and collar, mix the channels red-heavy
     (smooths skin, like a red filter on B&W film), stretch the tones using
     the face only so skin spans the ramp, add local contrast, then a 2.0
     gamma so only the real highlights get the densest glyphs
  3. each character cell takes the glyph whose ink coverage matches its tone
  4. cells that would be (near) blank but sit on a strong, consistent edge
     get a stroke along it (| / - \\), which is what draws the hair, brows,
     collar and jacket folds
  5. one <text> per row, revealed by a left-to-right clip wipe with a block
     cursor riding it; set STATIC=1 to skip the animation

The photo itself is never committed, only the SVG.
"""
import argparse
import html
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "portrait.svg")

COLS = 160
CW, CH = 8, 15                # sampling cell, same 8:15 shape as a monospace glyph
ROWS = round(COLS * CW / CH)

# glyphs ordered by how much ink they put down, measured in SF Mono Semibold
# relative to "0"; picked to avoid long runs of directional marks like - or =
RAMP = " .,:;!+vcoa@#0"
COVER = np.array([0, .135, .185, .272, .32, .363, .472, .532, .588, .681, .708, .774, .895, 1.0])
STROKE_ON = " .,"             # only light cells are replaced by edge strokes

CHANNEL_MIX = (0.55, 0.35, 0.10)
CROP = 2.0                    # square side, in face heights
ABOVE = 0.55                  # room above the face box for hair, in face heights
FACE_PCT = (3, 99.5)
LOCAL_CONTRAST = 0.5
GAMMA = 2.0
OUTLINE = 0.25
EDGE_PCT = 65

# --illustration
BG_TOLERANCE = 28             # summed RGB distance from the border colour that still counts as background
INK_GROW = 5                  # min-filter size that thickens dark outlines
DRAWING_PCT = (2, 98)
DRAWING_LOCAL_CONTRAST = 0.6
DRAWING_GAMMA = 1.8

# 840 x 880, same as stats.svg so the two panels match side by side
PAD = 20
BAR_H = 30
ART = 800
STATUS_H = 42
W, H = ART + 2 * PAD, BAR_H + 8 + ART + STATUS_H

BG, BG_TOP = "#0d1117", "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"

PRINT_TIME = 6.0              # seconds for the whole portrait to type out


def to_float(img):
    return np.asarray(img, dtype=np.float32) / 255


def to_img(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def blur(a, r):
    return to_float(to_img(a).filter(ImageFilter.GaussianBlur(r)))


def cutout(photo):
    with tempfile.TemporaryDirectory() as tmp:
        mask_path = os.path.join(tmp, "mask.png")
        res = subprocess.run(["swift", os.path.join(HERE, "cutout.swift"), photo, mask_path],
                             capture_output=True, text=True)
        if res.returncode:
            sys.exit(res.stderr.strip() or "cutout.swift failed")
        mask = Image.open(mask_path).convert("L")
        mask.load()
    face = json.loads(res.stdout.strip().splitlines()[-1])["face"]
    if not face:
        sys.exit("no face found, use a straight-on photo")
    return mask, face


def trim_shadow(on, face_cx, side):
    """Mirror the clean side's outline across the face to cut a shadow off the other side."""
    out = on.copy()
    slack = int(0.012 * on.shape[1])
    for y in range(on.shape[0]):
        xs = np.flatnonzero(on[y])
        if not len(xs):
            continue
        if side == "right" and xs[0] > 1:
            out[y, int(2 * face_cx - xs[0]) + slack:] = False
        elif side == "left" and xs[-1] < on.shape[1] - 2:
            out[y, :max(0, int(2 * face_cx - xs[-1]) - slack)] = False
    return out


def prepare(photo, shadow_side=None):
    im = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
    mask, face = cutout(photo)
    on = to_float(mask.resize(im.size)) > 0.5
    fx, fy, fw, fh = face[0] * im.width, face[1] * im.height, face[2] * im.width, face[3] * im.height
    if shadow_side:
        on = trim_shadow(on, fx + fw / 2, shadow_side)

    gray = to_float(im) @ np.array(CHANNEL_MIX, np.float32)
    side = fh * CROP
    box = tuple(round(v) for v in (fx + fw / 2 - side / 2, fy - fh * ABOVE, fx + fw / 2 + side / 2, fy - fh * ABOVE + side))
    # PIL fills outside the photo with 0, which the mask then keeps as background
    g = to_float(to_img(gray).crop(box).resize((ART, ART), Image.LANCZOS))
    m = to_float(to_img(on.astype(np.float32)).crop(box).resize((ART, ART), Image.LANCZOS))

    s = ART / side
    inset = 0.12 * fw * s
    x0, y0 = (fx - box[0]) * s, (fy - box[1]) * s
    skin = g[int(y0 + inset):int(y0 + fh * s - inset), int(x0 + inset):int(x0 + fw * s - inset)]
    lo, hi = np.percentile(skin, FACE_PCT)
    g = np.clip((g - lo) / max(hi - lo, 1e-3), 0, 1)
    g = np.clip(g + LOCAL_CONTRAST * (g - blur(g, 30)), 0, 1) ** GAMMA

    m = blur(m, 1.0)
    return g * m, m


def prepare_drawing(path):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                  (im.width + side) // 2, (im.height + side) // 2))
    rgb = np.asarray(im, dtype=np.float32)

    # background = border-coloured pixels reachable from the edges
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    near = np.abs(rgb - np.median(border, axis=0)).sum(-1) < BG_TOLERANCE
    fill = Image.fromarray(near.astype(np.uint8) * 255).copy()   # copy: arrays come in read-only
    for i in range(0, side, 16):
        for xy in ((i, 0), (i, side - 1), (0, i), (side - 1, i)):
            if fill.getpixel(xy) == 255:
                ImageDraw.floodfill(fill, xy, 128)
    subject = np.asarray(fill) != 128

    m = to_float(to_img(subject.astype(np.float32)).resize((ART, ART), Image.LANCZOS))
    g = to_float(im.convert("L").resize((ART, ART), Image.LANCZOS).filter(ImageFilter.MinFilter(INK_GROW)))

    lo, hi = np.percentile(g[m > 0.5], DRAWING_PCT)
    g = np.clip((g - lo) / max(hi - lo, 1e-3), 0, 1)
    g = np.clip(g + DRAWING_LOCAL_CONTRAST * (g - blur(g, 30)), 0, 1) ** DRAWING_GAMMA
    m = blur(m, 1.0)
    return g * m, m


def strokes(tone):
    """Per-cell edge mask and the stroke glyph that runs along each edge."""
    big = to_float(to_img(tone).resize((COLS * CW, ROWS * CH), Image.LANCZOS))
    gy, gx = np.gradient(blur(big, 1.5))
    cell = lambda a: a.reshape(ROWS, CH, COLS, CW).mean((1, 3))
    jxx, jyy, jxy = cell(gx * gx), cell(gy * gy), cell(gx * gy)
    # structure tensor: dominant gradient angle and how consistent it is
    theta = np.degrees(0.5 * np.arctan2(2 * jxy, jxx - jyy)) % 180
    trace = jxx + jyy
    coherence = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (trace + 1e-9)
    strength = trace * coherence
    edge = strength > np.percentile(strength, EDGE_PCT)
    # the edge runs perpendicular to the gradient; image y points down
    glyph = np.where((theta < 22.5) | (theta >= 157.5), "|",
                     np.where(theta < 67.5, "\\", np.where(theta < 112.5, "-", "/")))
    return edge, glyph


def to_rows(tone, mask):
    cells = lambda a: to_float(to_img(a).resize((COLS, ROWS), Image.BOX))
    ink, inside = cells(tone), cells(mask)

    # lift the silhouette edge a little so the head shape survives in the dark
    gy, gx = np.gradient(inside)
    outline = np.clip((np.abs(gx) + np.abs(gy)) * 2, 0, 1) * OUTLINE
    ink = np.maximum(ink, outline)

    idx = np.abs(ink[..., None] - COVER[None, None, :]).argmin(-1)
    chars = np.array(list(RAMP))[idx]
    chars[(inside < 0.5) & (outline < 0.05)] = " "

    edge, glyph = strokes(tone)
    swap = edge & np.isin(chars, list(STROKE_ON))
    chars[swap] = glyph[swap]
    return ["".join(r).rstrip() for r in chars]


def render(rows, static=False):
    cell_w = ART / COLS
    cell_h = ART / len(rows)
    row_time = PRINT_TIME / len(rows)
    art_y = BAR_H + 8

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{BAR_H}" x2="{W}" y2="{BAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{PAD + i * 16}" cy="{BAR_H / 2}" r="5" fill="{dot}"/>')
    out.append(f'<text x="{W / 2}" y="{BAR_H / 2 + 4}" fill="{MUTED}" font-size="12" text-anchor="middle">'
               'daksh@github: ~$ ./portrait.sh</text>')

    out.append(f'<g fill="{INK}" font-size="{cell_h * 0.9:.2f}" font-weight="600">')
    for r, line in enumerate(rows):
        if not line:
            continue
        top = art_y + r * cell_h
        width = len(line) * cell_w
        # textLength pins every row to the grid whatever monospace font the viewer has
        text = (f'<text xml:space="preserve" x="{PAD}" y="{top + cell_h * 0.78:.1f}" '
                f'textLength="{width:.1f}" lengthAdjust="spacing">{html.escape(line)}</text>')
        if static:
            out.append(text)
            continue
        start = r * row_time
        out.append(f'<clipPath id="r{r}"><rect x="{PAD}" y="{top:.1f}" height="{cell_h:.1f}" width="0">'
                   f'<animate attributeName="width" to="{width:.1f}" begin="{start:.3f}s" dur="{row_time:.3f}s" '
                   f'fill="freeze"/></rect></clipPath><g clip-path="url(#r{r})">{text}</g>')
        out.append(f'<rect y="{top + 1:.1f}" width="{cell_w:.1f}" height="{cell_h - 2:.1f}" opacity="0">'
                   f'<animate attributeName="x" from="{PAD}" to="{PAD + width:.1f}" begin="{start:.3f}s" '
                   f'dur="{row_time:.3f}s" fill="freeze"/>'
                   f'<set attributeName="opacity" to=".85" begin="{start:.3f}s"/>'
                   f'<set attributeName="opacity" to="0" begin="{start + row_time:.3f}s"/></rect>')
    out.append('</g>')

    line_y = art_y + ART + 6
    text_y = line_y + 23
    prompt = "daksh@github:~$ whoami "
    name = "Daksh Tyagi"
    out.append(f'<line x1="0" y1="{line_y}" x2="{W}" y2="{line_y}" stroke="{FRAME}"/>')
    out.append(f'<text x="{PAD}" y="{text_y}" fill="{MUTED}" font-size="14">{prompt}'
               f'<tspan fill="{INK}">{name}</tspan></text>')
    # blinking block cursor after the name (14px monospace is ~8.4px per glyph)
    out.append(f'<rect x="{PAD + (len(prompt + name) + 1) * 8.4:.1f}" y="{text_y - 12}" width="8" height="15" '
               f'fill="{INK}"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.51;1" '
               'dur="1s" repeatCount="indefinite"/></rect>')

    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("photo")
    ap.add_argument("out", nargs="?", default=OUT)
    ap.add_argument("--trim-shadow", choices=["left", "right"],
                    help="side of the subject with a wall shadow to cut off")
    ap.add_argument("--illustration", action="store_true",
                    help="source is a drawing on a plain background, not a photo")
    args = ap.parse_args()

    if args.illustration:
        rows = to_rows(*prepare_drawing(args.photo))
    else:
        rows = to_rows(*prepare(args.photo, args.trim_shadow))
    svg = render(rows, static=bool(os.environ.get("STATIC")))
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"wrote {args.out} ({len(svg) // 1024} KB, {COLS}x{len(rows)} chars)")
    if os.environ.get("ASCII"):
        print("\n".join(rows))
