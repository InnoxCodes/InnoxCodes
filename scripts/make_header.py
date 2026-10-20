#!/usr/bin/env python3
"""
Render the README header (assets/header.svg): a terminal window where
"Hi, I'm Daksh" types itself out and the role lines below it type and erase
on a loop.

Typing is done with SMIL: a clip rect whose width steps one character at a
time (calcMode="discrete"), with a block cursor stepping along with it.
textLength pins every line to the exact character grid, so the clip and the
cursor stay in sync whatever monospace font the viewer ends up with.

The header doesn't depend on any data, so it only needs re-running when the
text below changes.

    python3 scripts/make_header.py
"""
import html
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "assets", "header.svg")

NAME = "Hi, I'm Daksh"
ROLES = [
    "Software Engineer | AI Specialist",
    "RAG pipelines + LLM-powered backends",
    "I turn prompts into production.",
]

W, H = 860, 250
PAD = 28
BAR_H = 30

BG, BG_TOP = "#0d1117", "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"
GREEN = "#39d353"
CYAN = "#00d9ff"

ADVANCE = 0.6                  # monospace glyph width, in em

# seconds
NAME_AT, NAME_STEP = 0.8, 0.09
ROLES_AT = 2.9
TYPE_STEP, ERASE_STEP = 0.045, 0.02
HOLD, GAP = 2.4, 0.35


def text(x, y, s, size, fill, weight=400, extra=""):
    width = len(s) * size * ADVANCE
    return (f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'textLength="{width:.1f}" lengthAdjust="spacingAndGlyphs" xml:space="preserve"{extra}>'
            f'{html.escape(s)}</text>')


def steps(frames, total):
    """[(time, value)] -> SMIL values/keyTimes over a cycle of `total` seconds."""
    values = ";".join(f"{v:.1f}" for _, v in frames)
    times = ";".join(f"{t / total:.4f}" for t, _ in frames)
    return f'values="{values}" keyTimes="{times}" calcMode="discrete"'


def typed_once(x, y, s, size, fill, weight, start, step, clip_id):
    """A line that types itself in once and stays."""
    cw = size * ADVANCE
    n = len(s)
    dur = n * step
    frames = [(k * step, k * cw) for k in range(n + 1)]
    cursor = [(t, x + v) for t, v in frames]
    return (
        f'<clipPath id="{clip_id}"><rect x="{x}" y="{y - size}" height="{size * 1.3:.1f}" width="0">'
        f'<animate attributeName="width" begin="{start}s" dur="{dur:.3f}s" fill="freeze" {steps(frames, dur)}/>'
        f'</rect></clipPath>'
        f'<g clip-path="url(#{clip_id})">{text(x, y, s, size, fill, weight)}</g>'
        f'<rect y="{y - size * 0.8:.1f}" width="{cw * 0.55:.1f}" height="{size * 0.95:.1f}" fill="{fill}" opacity="0">'
        f'<animate attributeName="x" begin="{start}s" dur="{dur:.3f}s" fill="freeze" {steps(cursor, dur)}/>'
        f'<set attributeName="opacity" to=".9" begin="{start}s"/>'
        f'<set attributeName="opacity" to="0" begin="{start + dur + 0.6:.2f}s"/></rect>'
    )


def render():
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<style>'
        '.in{opacity:0;animation:in .5s ease-out both}'
        '@keyframes in{from{opacity:0;transform:translateX(8px)}to{opacity:1;transform:none}}'
        '@media (prefers-reduced-motion:reduce){.in{opacity:1;animation:none}}'
        '</style>',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient>'
        f'<radialGradient id="glow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" '
        f'gradientTransform="translate(150 120) scale(320 150)"><stop offset="0" stop-color="{CYAN}" stop-opacity=".09"/>'
        f'<stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#glow)"/>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{BAR_H}" x2="{W}" y2="{BAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{20 + i * 16}" cy="{BAR_H / 2}" r="5" fill="{dot}"/>')
    out.append(f'<text x="{W / 2}" y="{BAR_H / 2 + 4}" fill="{MUTED}" font-size="12" text-anchor="middle">'
               'daksh@github: ~</text>')

    # left: prompt, typed name, prompt, rotating roles
    out.append(f'<g class="in" style="animation-delay:.2s">{text(PAD, 70, "daksh@github:~$", 15, GREEN)}'
               f'{text(PAD + 16 * 15 * ADVANCE, 70, "whoami", 15, INK)}</g>')
    out.append(typed_once(PAD, 124, NAME, 44, CYAN, 700, NAME_AT, NAME_STEP, "name"))
    out.append(f'<g class="in" style="animation-delay:{ROLES_AT - 0.6:.1f}s">{text(PAD, 170, "daksh@github:~$", 15, GREEN)}'
               f'{text(PAD + 16 * 15 * ADVANCE, 170, "cat roles.txt", 15, INK)}</g>')

    size, y = 20, 210
    cw = size * ADVANCE
    lengths = [len(r) for r in ROLES]
    slots = [n * TYPE_STEP + HOLD + n * ERASE_STEP + GAP for n in lengths]
    cycle = sum(slots)
    cursor = []
    start = 0.0
    for i, (role, n, slot) in enumerate(zip(ROLES, lengths, slots)):
        frames = [(0.0, 0.0)] if start > 0 else []
        frames += [(start + k * TYPE_STEP, k * cw) for k in range(n + 1)]
        held = start + n * TYPE_STEP + HOLD
        frames += [(held + (n - k) * ERASE_STEP, k * cw) for k in range(n - 1, -1, -1)]
        frames.append((cycle, 0.0))
        cursor += [(t, PAD + v) for t, v in frames[:-1] if t >= start]
        out.append(
            f'<clipPath id="role{i}"><rect x="{PAD}" y="{y - size}" height="{size * 1.4:.1f}" width="0">'
            f'<animate attributeName="width" begin="{ROLES_AT}s" dur="{cycle:.3f}s" repeatCount="indefinite" '
            f'{steps(frames, cycle)}/></rect></clipPath>'
            f'<g clip-path="url(#role{i})">{text(PAD, y, role, size, INK)}</g>'
        )
        start += slot
    cursor.append((cycle, PAD))
    out.append(
        f'<rect x="{PAD}" y="{y - size * 0.8:.1f}" width="{cw * 0.55:.1f}" height="{size:.1f}" fill="{CYAN}" opacity="0">'
        f'<animate attributeName="x" begin="{ROLES_AT}s" dur="{cycle:.3f}s" repeatCount="indefinite" {steps(cursor, cycle)}/>'
        f'<animate attributeName="opacity" begin="{ROLES_AT}s" dur="1s" values="1;0" calcMode="discrete" '
        f'repeatCount="indefinite"/></rect>'
    )

    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    svg = render()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(svg) // 1024} KB)")
