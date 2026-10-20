#!/usr/bin/env python3
"""
Render the numbers card that sits next to the ASCII portrait: six stat tiles
whose values count up, then a contributions-per-month bar chart that grows in.

The canvas matches the portrait (840 x 880) so both panels end up the same
height when the README shows them at the same width. Font sizes are doubled
for that reason, since each panel is displayed at roughly half size.

The count-up is a stack of pre-rendered numbers switched on and off with SMIL
<set>, because there's no JS inside a README image.

    python scripts/render_stats.py
"""
import datetime as dt
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "data", "contributions.json")
OUT = os.path.join(ROOT, "assets", "stats.svg")

BG, BG_TOP = "#0d1117", "#111722"
TILE = "#161b22"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"
GREEN = "#39d353"
BAR = "#26a641"
CYAN = "#00d9ff"

W, H = 840, 880
PAD = 20
BAR_H = 30
GAP = 16
TILE_W = (W - 2 * PAD - GAP) / 2
TILE_H = 150
TILES_Y = BAR_H + PAD + 4
CHART_Y = TILES_Y + 3 * (TILE_H + GAP)

# seconds
STAGGER = 0.15
SLIDE = 0.45
COUNT = 1.2
FRAMES = 16
BARS_AT = 6 * STAGGER + 0.4
BAR_STAGGER = 0.06
GROW = 0.6


def short(iso):
    return dt.date.fromisoformat(iso).strftime("%b %-d")


def span(streak):
    if not streak["length"]:
        return "start one today"
    if streak["start"] == streak["end"]:
        return short(streak["start"])
    return f'{short(streak["start"])} &#8211; {short(streak["end"])}'


def number(v, like):
    return f"{v:,.1f}" if isinstance(like, float) else f"{round(v):,}"


def render(data):
    n_days = len(data["days"])
    cur, lng, best = data["current_streak"], data["longest_streak"], data["best_day"]
    tiles = [
        ("current streak", cur["length"], " days", span(cur), GREEN),
        ("longest streak", lng["length"], " days", span(lng), INK),
        ("contributions", data["total"], "", "in the last year", INK),
        ("active days", data["active_days"], f" / {n_days}", f'{data["active_days"] / n_days:.0%} of the year', INK),
        ("best day", best["count"], "", short(best["date"]), INK),
        ("avg / active day", float(data["avg_per_active_day"]), "", "contributions", INK),
    ]

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<style>'
        f'.t{{opacity:0;animation:rise {SLIDE}s ease-out both}}'
        '@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}'
        f'.b{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow {GROW}s ease-out both}}'
        '@keyframes grow{to{transform:scaleY(1)}}'
        '@media (prefers-reduced-motion:reduce){.t,.b{opacity:1;transform:none;animation:none}}'
        '</style>',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{BAR_H}" x2="{W}" y2="{BAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{PAD + i * 16}" cy="{BAR_H / 2}" r="5" fill="{dot}"/>')
    out.append(f'<text x="{W / 2}" y="{BAR_H / 2 + 4}" fill="{MUTED}" font-size="12" text-anchor="middle">'
               'daksh@github: ~$ ./stats.sh</text>')

    for i, (label, value, suffix, caption, colour) in enumerate(tiles):
        x = PAD + (i % 2) * (TILE_W + GAP)
        y = TILES_Y + (i // 2) * (TILE_H + GAP)
        start = i * STAGGER
        counting = start + SLIDE * 0.6

        out.append(f'<g class="t" style="animation-delay:{start:.2f}s">')
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{TILE_W:.1f}" height="{TILE_H}" rx="10" '
                   f'fill="{TILE}" stroke="{FRAME}"/>')
        out.append(f'<text x="{x + 24:.1f}" y="{y + 40}" fill="{MUTED}" font-size="22">$ {label}</text>')
        for k in range(1, FRAMES + 1):
            shown = value * (1 - (1 - k / FRAMES) ** 3)   # ease out into the real number
            on = counting + COUNT * (k - 1) / FRAMES
            sets = f'<set attributeName="opacity" to="1" begin="{on:.3f}s"/>'
            if k < FRAMES:
                sets += f'<set attributeName="opacity" to="0" begin="{on + COUNT / FRAMES:.3f}s"/>'
            out.append(f'<text x="{x + 24:.1f}" y="{y + 100}" opacity="0" font-size="54" font-weight="700" '
                       f'fill="{colour}">{number(shown, value)}<tspan font-size="24" font-weight="400" '
                       f'fill="{MUTED}">{suffix}</tspan>{sets}</text>')
        out.append(f'<text x="{x + 24:.1f}" y="{y + 132}" fill="{MUTED}" font-size="20">{caption}</text>')
        out.append('</g>')

    months = data["monthly"]
    chart_h = H - PAD - CHART_Y
    out.append(f'<g class="t" style="animation-delay:{BARS_AT - 0.3:.2f}s">'
               f'<rect x="{PAD}" y="{CHART_Y}" width="{W - 2 * PAD}" height="{chart_h}" rx="10" '
               f'fill="{TILE}" stroke="{FRAME}"/>'
               f'<text x="{PAD + 24}" y="{CHART_Y + 40}" fill="{MUTED}" font-size="22">$ contributions / month</text></g>')

    top, bottom = CHART_Y + 70, CHART_Y + chart_h - 40
    left, right = PAD + 24, W - PAD - 24
    slot = (right - left) / len(months)
    bar_w = slot * 0.62
    peak = max(m["total"] for m in months) or 1
    for i, m in enumerate(months):
        h = max(3, (bottom - top) * m["total"] / peak)
        bx = left + i * slot + (slot - bar_w) / 2
        delay = BARS_AT + i * BAR_STAGGER
        is_peak = m["total"] == peak
        fill = GREEN if is_peak else BAR if m["total"] else FRAME
        out.append(f'<rect class="b" x="{bx:.1f}" y="{bottom - h:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="3" '
                   f'fill="{fill}" style="animation-delay:{delay:.2f}s"><title>{m["month"]}: {m["total"]:,}</title></rect>')
        initial = dt.date.fromisoformat(m["month"] + "-01").strftime("%b")[0]
        out.append(f'<text x="{bx + bar_w / 2:.1f}" y="{bottom + 28}" fill="{MUTED}" font-size="18" '
                   f'text-anchor="middle">{initial}</text>')
        if is_peak:
            out.append(f'<text class="t" style="animation-delay:{delay + GROW:.2f}s" x="{bx + bar_w / 2:.1f}" '
                       f'y="{bottom - h - 10:.1f}" fill="{CYAN}" font-size="18" text-anchor="middle">{peak:,}</text>')

    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    svg = render(json.load(open(SRC)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(svg) // 1024} KB)")
