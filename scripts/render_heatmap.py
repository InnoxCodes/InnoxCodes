#!/usr/bin/env python3
"""
Draw data/contributions.json as a contribution calendar inside a terminal
window. Empty days are faint dots so the active days read as the pattern;
active days pop in with a soft glow, and today's square gets a blinking
cursor around it.

The grid takes turns revealing itself three ways, on a loop:
  ripple  a wave spreading back through the year from today
  scan    a cyan beam sweeps left to right and lights days as it passes
  rain    each week falls into place at its own moment, matrix style

Each style is its own copy of the grid in a <g> that is only visible during
its slot. Every cell animation runs on the full cycle length with its delay
pushed into its slot, so one shared set of keyframes serves all ~370 cells.

GitHub strips JS from READMEs but plays CSS animations inside SVGs loaded
through <img>, which is all this relies on.

    python scripts/render_heatmap.py [--styles ripple,scan,rain] [output.svg]
"""
import argparse
import datetime as dt
import json
import math
import os
import random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "data", "contributions.json")
OUT = os.path.join(ROOT, "assets", "contrib-heatmap.svg")

# GitHub dark theme greens, level 0 (none) to 4 (most)
SHADES = ["#262c36", "#0e4429", "#006d32", "#26a641", "#39d353"]
DOT = 0.4          # empty days are drawn at this fraction of a full cell
BG, BG_TOP = "#0d1117", "#111722"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"
GREEN = "#39d353"
CYAN = "#00d9ff"   # same cyan as the typing header at the top of the README
GOLD = "#ffd700"

W = 860            # README shows it at 860px, so 1 unit == 1 css px
PAD = 22
BAR_H = 30         # title bar
DAY_LABEL_W = 34
MONTH_LABEL_H = 22
FOOTER_H = 94     # legend row, divider, two stat lines and bottom padding

# timings, in seconds
SLOT = 7.0            # each style's turn: reveal, hold, fade out
FADE = 0.5
RIPPLE_STEP = 0.035   # per cell of distance from today
SWEEP = 2.4           # scan beam crossing the whole grid
RAIN_SPREAD = 1.4     # columns start somewhere in this window
POP = 0.55


def reveal_delays(cols, today, style):
    """Seconds before each (column, row) appears."""
    rng = random.Random(7)   # fixed seed so the daily rebuild doesn't churn the file
    col_start = [rng.uniform(0, RAIN_SPREAD) for _ in cols]
    delays = {}
    for ci, col in enumerate(cols):
        for ri in range(7):
            if style == "ripple":
                delays[ci, ri] = math.hypot(ci - today[0], ri - today[1]) * RIPPLE_STEP
            elif style == "scan":
                delays[ci, ri] = SWEEP * ci / len(cols)
            else:
                delays[ci, ri] = col_start[ci] + ri * 0.07
    return delays


def weeks(days):
    """Group days into Sunday-first columns, padding the first and last week."""
    cols, col = [], []
    first = dt.date.fromisoformat(days[0]["date"])
    col.extend([None] * ((first.weekday() + 1) % 7))
    for d in days:
        col.append(d)
        if len(col) == 7:
            cols.append(col)
            col = []
    if col:
        cols.append(col + [None] * (7 - len(col)))
    return cols


def short(iso):
    return dt.date.fromisoformat(iso).strftime("%b %-d")


def render(data, styles=("ripple", "scan", "rain")):
    cols = weeks(data["days"])
    grid_x = PAD + DAY_LABEL_W
    grid_y = BAR_H + MONTH_LABEL_H
    step = (W - grid_x - PAD) / len(cols)
    cell = round(step * 0.8, 1)
    H = grid_y + 7 * step + FOOTER_H

    today = next((ci, ri) for ci in range(len(cols) - 1, -1, -1)
                 for ri in range(6, -1, -1) if cols[ci][ri])
    T = SLOT * len(styles)
    run = len(cols) * step

    def at(t):
        return f"{100 * t / T:.2f}%"

    # A cell's loop restarts at its own delay, so without this it would still
    # be lit from the last round when its style's turn comes back and then
    # re-pop. Hiding it one slot after it appeared (by then its group is
    # already invisible) means each turn starts from an empty grid.
    hide = min(SLOT, T - .05)
    gone = f'{at(hide + .01)},100%{{opacity:0}}'

    css = [
        '.e,.a,.f{transform-box:fill-box;transform-origin:center}',
        f'.e{{opacity:0;animation:fade {T}s linear infinite}}',
        f'.a{{opacity:0;animation:pop {T}s cubic-bezier(.2,.9,.3,1.3) infinite}}',
        f'.f{{opacity:0;animation:fall {T}s cubic-bezier(.2,.9,.3,1.1) infinite}}',
        f'.g{{opacity:0;animation:glow {T}s ease-out infinite}}',
        f'.beam{{opacity:0;animation:sweep {T}s linear infinite}}',
        '.k{opacity:0;animation:blink 1.1s step-end infinite}',
        f'@keyframes fade{{0%{{opacity:0}}{at(.4)},{at(hide)}{{opacity:1}}{gone}}}',
        f'@keyframes pop{{0%{{opacity:0;transform:scale(.2)}}{at(POP * .6)}{{opacity:1;transform:scale(1.35)}}'
        f'{at(POP)},{at(hide)}{{opacity:1;transform:none}}{gone}}}',
        f'@keyframes fall{{0%{{opacity:0;transform:translateY(-26px)}}{at(POP)},{at(hide)}{{opacity:1;transform:none}}{gone}}}',
        f'@keyframes glow{{0%{{opacity:0}}{at(.42)}{{opacity:.9}}{at(1.4)},{at(hide)}{{opacity:.45}}{gone}}}',
        f'@keyframes sweep{{0%{{opacity:0;transform:none}}{at(.1)},{at(SWEEP * .92)}{{opacity:1}}'
        f'{at(SWEEP)},100%{{opacity:0;transform:translateX({run:.0f}px)}}}}',
        '@keyframes blink{0%{opacity:1}50%{opacity:0}}',
    ]
    # slot visibility for each copy of the grid
    for i in range(len(styles)):
        if len(styles) == 1:
            break
        s0, s1 = i * SLOT, (i + 1) * SLOT
        hidden_before = f'0%,{at(s0 - .01)}{{opacity:0}}' if i else ''
        css.append(f'.p{i}{{animation:p{i} {T}s linear infinite}}'
                   f'@keyframes p{i}{{{hidden_before}{at(s0)},{at(s1 - FADE)}{{opacity:1}}{at(s1)},100%{{opacity:0}}}}')
    css.append('@media (prefers-reduced-motion:reduce){.e,.a,.f,.g,.p0{opacity:1;animation:none}'
               + ''.join(f'.p{i},' for i in range(1, len(styles))) + '.beam,.k{display:none}}')

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H:.0f}" viewBox="0 0 {W} {H:.0f}" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f'<style>{"".join(css)}</style>',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient>'
        f'<linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{CYAN}" stop-opacity=".55"/></linearGradient>'
        '<filter id="blur" x="-150%" y="-150%" width="400%" height="400%"><feGaussianBlur stdDeviation="3"/></filter>'
        '</defs>',
        f'<rect width="{W}" height="{H:.0f}" rx="12" fill="url(#bg)"/>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1:.0f}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{BAR_H}" x2="{W}" y2="{BAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        out.append(f'<circle cx="{PAD + i * 16}" cy="{BAR_H / 2}" r="5" fill="{dot}"/>')
    out.append(f'<text x="{W / 2}" y="{BAR_H / 2 + 4}" fill="{MUTED}" font-size="12" text-anchor="middle">'
               'daksh@github: ~/contributions --graph</text>')

    # label each column where the month changes; a stub month at the left edge
    # that would collide with the next label is dropped, like GitHub does
    labels, prev = [], None
    for ci, col in enumerate(cols):
        date = dt.date.fromisoformat(next(d for d in col if d)["date"])
        if date.month != prev:
            labels.append((ci, date.strftime("%b")))
        prev = date.month
    if len(labels) > 1 and labels[1][0] - labels[0][0] < 3:
        labels.pop(0)
    for ci, name in labels:
        out.append(f'<text x="{grid_x + ci * step:.1f}" y="{BAR_H + 15}" fill="{MUTED}" font-size="11">{name}</text>')

    for row, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        out.append(f'<text x="{PAD}" y="{grid_y + row * step + cell * 0.8:.1f}" fill="{MUTED}" '
                   f'font-size="10">{name}</text>')

    dot = round(cell * DOT, 1)
    first_done = None
    for i, style in enumerate(styles):
        delays = reveal_delays(cols, today, style)
        first_done = first_done or max(delays.values()) + POP
        enter = "f" if style == "rain" else "a"   # rain falls in, the others pop out of the dot
        halos, cells = [], []
        for ci, col in enumerate(cols):
            for ri, d in enumerate(col):
                if not d:
                    continue
                x, y = grid_x + ci * step, grid_y + ri * step
                delay = f'style="animation-delay:{i * SLOT + delays[ci, ri]:.3f}s"'
                if not d["level"]:
                    off = (cell - dot) / 2
                    cells.append(f'<rect class="e" x="{x + off:.1f}" y="{y + off:.1f}" width="{dot}" height="{dot}" '
                                 f'rx="{dot / 2}" fill="{SHADES[0]}" {delay}/>')
                    continue
                colour = SHADES[d["level"]]
                if d["level"] >= 2:
                    halos.append(f'<rect class="g" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" '
                                 f'fill="{colour}" filter="url(#blur)" {delay}/>')
                cells.append(f'<rect class="{enter}" x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" '
                             f'rx="2.5" fill="{colour}" {delay}/>')
        out.append(f'<g class="p{i}">')
        out += halos + cells   # glows underneath so they never cover a neighbour
        if style == "scan":
            out.append(f'<rect class="beam" x="{grid_x - 26}" y="{grid_y - 6}" width="26" '
                       f'height="{7 * step + 8:.1f}" fill="url(#beam)" style="animation-delay:{i * SLOT}s"/>')
        out.append('</g>')

    # today: a cursor outline that starts blinking once the first reveal lands
    tx, ty = grid_x + today[0] * step, grid_y + today[1] * step
    out.append(f'<rect class="k" x="{tx - 2:.1f}" y="{ty - 2:.1f}" width="{cell + 4}" height="{cell + 4}" rx="3.5" '
               f'fill="none" stroke="{CYAN}" stroke-width="1.5" style="animation-delay:{first_done:.2f}s"/>')

    # Less . [] [] [] [] More, right-aligned under the grid
    key_y = grid_y + 7 * step + 4
    key_x = W - PAD - 34 - len(SHADES) * (cell + 3)
    out.append(f'<text x="{key_x - 6:.1f}" y="{key_y + cell * 0.82:.1f}" fill="{MUTED}" font-size="10" '
               'text-anchor="end">Less</text>')
    for i, shade in enumerate(SHADES):
        size, off = (dot, (cell - dot) / 2) if i == 0 else (cell, 0)
        out.append(f'<rect x="{key_x + i * (cell + 3) + off:.1f}" y="{key_y + off:.1f}" width="{size}" '
                   f'height="{size}" rx="{size / 2 if i == 0 else 2.5}" fill="{shade}"/>')
    out.append(f'<text x="{W - PAD}" y="{key_y + cell * 0.82:.1f}" fill="{MUTED}" font-size="10" '
               'text-anchor="end">More</text>')

    rule_y = key_y + cell + 12
    out.append(f'<line x1="0" y1="{rule_y:.1f}" x2="{W}" y2="{rule_y:.1f}" stroke="{FRAME}"/>')

    cur, lng, best = data["current_streak"], data["longest_streak"], data["best_day"]
    y1, y2 = rule_y + 24, rule_y + 46
    out.append(f'<text x="{PAD}" y="{y1:.1f}" font-size="13" fill="{MUTED}">'
               f'<tspan fill="{GREEN}" font-weight="700">{data["total"]:,}</tspan> contributions in the last year</text>')
    out.append(f'<text x="{W - PAD}" y="{y1:.1f}" font-size="12" fill="{MUTED}" text-anchor="end">'
               f'{short(data["days"][0]["date"])} &#8594; {short(data["days"][-1]["date"])}</text>')
    out.append(f'<text x="{PAD}" y="{y2:.1f}" font-size="13" fill="{MUTED}">current streak '
               f'<tspan fill="{CYAN}" font-weight="700">{cur["length"]} days</tspan>  &#183;  longest '
               f'<tspan fill="{CYAN}" font-weight="700">{lng["length"]} days</tspan></text>')
    out.append(f'<text x="{W - PAD}" y="{y2:.1f}" font-size="12" fill="{MUTED}" text-anchor="end">best day '
               f'<tspan fill="{GOLD}" font-weight="700">{best["count"]}</tspan> on {short(best["date"])}</text>')

    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles", default="ripple,scan,rain", help="comma separated, played in this order")
    ap.add_argument("out", nargs="?", default=OUT)
    args = ap.parse_args()
    styles = args.styles.split(",")
    if not styles or set(styles) - {"ripple", "scan", "rain"}:
        ap.error("styles must be ripple, scan and/or rain")
    svg = render(json.load(open(SRC)), styles)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(svg)
    print(f"wrote {args.out} ({"/".join(styles)}, {len(svg) // 1024} KB)")
