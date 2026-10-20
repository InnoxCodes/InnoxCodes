#!/usr/bin/env python3
"""
Pull the last year of daily contribution counts from the public calendar
fragment GitHub serves for every profile, and save them to
data/contributions.json together with the numbers the stats card shows.

No token needed. If GitHub changes the markup this exits non-zero, so the
workflow fails loudly instead of committing an empty graph.

    python scripts/fetch_contributions.py
"""
import datetime as dt
import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup

USER = os.environ.get("PROFILE_USER", "InnoxCodes")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "contributions.json")


def scrape():
    url = f"https://github.com/users/{USER}/contributions"
    res = requests.get(url, headers={"User-Agent": f"{USER}-profile-readme"}, timeout=30)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    # each cell's count only lives in its <tool-tip>, linked by the cell id
    tips = {t.get("for"): t.get_text(" ", strip=True) for t in soup.find_all("tool-tip")}

    days = []
    for td in soup.select("td.ContributionCalendar-day[data-date]"):
        tip = tips.get(td.get("id"), "")
        m = re.match(r"([\d,]+) contributions?", tip)
        days.append({
            "date": td["data-date"],
            "count": int(m.group(1).replace(",", "")) if m else 0,
            # GitHub's own 0-4 shade, so the colours match the real graph
            "level": int(td.get("data-level") or 0),
        })

    if len(days) < 300:
        sys.exit(f"only found {len(days)} calendar cells, the page layout probably changed")
    return sorted(days, key=lambda d: d["date"])


def runs(days):
    """Yield (length, start, end) for every streak of non-zero days."""
    start = None
    for i, d in enumerate(days):
        if d["count"] and start is None:
            start = i
        if start is not None and (not d["count"] or i == len(days) - 1):
            end = i if d["count"] else i - 1
            yield end - start + 1, days[start]["date"], days[end]["date"]
            start = None


def summarise(days):
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"])

    longest = max(runs(days), default=(0, None, None))

    # today still has hours left, so a zero today shouldn't reset the streak
    tail = days[:-1] if days[-1]["count"] == 0 else days
    current = (0, None, None)
    for run in runs(tail):
        if run[2] == tail[-1]["date"]:
            current = run

    best = max(days, key=lambda d: d["count"])

    months = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["count"]

    as_dict = lambda r: {"length": r[0], "start": r[1], "end": r[2]}
    return {
        "user": USER,
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": total,
        "active_days": active,
        "avg_per_active_day": round(total / active, 1) if active else 0,
        "current_streak": as_dict(current),
        "longest_streak": as_dict(longest),
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": [{"month": k, "total": v} for k, v in sorted(months.items())],
        "days": days,
    }


if __name__ == "__main__":
    data = summarise(scrape())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
    print(f"{data['total']} contributions, {data['active_days']} active days, "
          f"streak {data['current_streak']['length']} (longest {data['longest_streak']['length']})")
