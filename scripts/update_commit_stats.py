#!/usr/bin/env python3
"""Generate per-year, commit-only contribution calendars for the GitHub profile."""
import datetime as dt
import html
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

USER = "nica7410"
FIRST_YEAR = 2020
TODAY = dt.datetime.now(dt.timezone.utc).date()
YEAR = TODAY.year
DATA_DIR = Path("assets/commit-years")
DATA_DIR.mkdir(parents=True, exist_ok=True)
COLOR = ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")


def fetch_days(days):
    result = {}
    # Small GraphQL batches avoid the excessive complexity of a single query.
    for offset in range(0, len(days), 20):
        batch = days[offset:offset + 20]
        aliases = []
        for i, day in enumerate(batch):
            next_day = day + dt.timedelta(days=1)
            aliases.append(
                f'd{i}: contributionsCollection('
                f'from: "{day}T00:00:00Z", to: "{next_day}T00:00:00Z") '
                '{ totalCommitContributions }'
            )
        query = 'query { user(login: "' + USER + '") { ' + ' '.join(aliases) + ' } }'
        request = Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query}).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + os.environ["GH_TOKEN"],
                "Content-Type": "application/json",
                "User-Agent": "commit-only-profile-calendar",
            },
            method="POST",
        )
        for attempt in range(3):
            try:
                with urlopen(request, timeout=60) as response:
                    payload = json.load(response)
                if payload.get("errors") or not payload.get("data", {}).get("user"):
                    raise RuntimeError(str(payload.get("errors", "Missing user")))
                for i, day in enumerate(batch):
                    result[day.isoformat()] = payload["data"]["user"][f"d{i}"]["totalCommitContributions"]
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    return result


def build_svg(year, counts):
    jan1 = dt.date(year, 1, 1)
    dec31 = dt.date(year, 12, 31)
    base = jan1 - dt.timedelta(days=(jan1.weekday() + 1) % 7)
    end = min(TODAY, dec31)
    weeks = (dec31 - base).days // 7 + 1
    max_count = max(counts.values(), default=0)
    total = sum(counts.values())
    left, top, step, cell = 42, 39, 14, 11
    width = left + weeks * step + 12

    def shade(n):
        if n == 0:
            return COLOR[0]
        return COLOR[min(4, 1 + (n * 4 - 1) // max(1, max_count))]

    fragments = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 164" '
        f'width="{width}" height="164" role="img" '
        f'aria-label="{year}: {total:,} commit contributions">',
        f'<text x="{left}" y="17" font-size="15" font-weight="600" '
        f'font-family="Arial,sans-serif" fill="#24292f">'
        f'{year}: {total:,} commit contributions</text>',
    ]
    for month in range(1, 13):
        day = dt.date(year, month, 1)
        column = (day - base).days // 7
        fragments.append(
            f'<text x="{left + column * step}" y="31" '
            f'font-size="11" font-family="Arial,sans-serif" fill="#57606a">'
            f'{html.escape(day.strftime("%b"))}</text>'
        )
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        fragments.append(
            f'<text x="6" y="{top + row * step + 9}" font-size="10" '
            f'font-family="Arial,sans-serif" fill="#57606a">{label}</text>'
        )
    cursor = jan1
    while cursor <= dec31:
        col = (cursor - base).days // 7
        row = (cursor.weekday() + 1) % 7
        count = counts.get(cursor.isoformat(), 0)
        color = shade(count) if cursor <= end else "#ffffff"
        fragments.append(
            f'<rect x="{left + col * step}" y="{top + row * step}" '
            f'width="{cell}" height="{cell}" rx="2" fill="{color}">'
            f'<title>{cursor.isoformat()}: {count} commits</title></rect>'
        )
        cursor += dt.timedelta(days=1)
    fragments.append(
        '<text x="42" y="155" font-size="11" font-family="Arial,sans-serif" '
        'fill="#57606a">Commits only · issues, PRs and reviews excluded</text></svg>'
    )
    return "".join(fragments), total


years = {}
for year in range(YEAR, FIRST_YEAR - 1, -1):
    first = dt.date(year, 1, 1)
    last = min(TODAY, dt.date(year, 12, 31))
    cache = DATA_DIR / f"{year}.json"
    if year < YEAR and cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
    else:
        days = [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]
        saved = fetch_days(days)
        cache.write_text(json.dumps(saved, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    svg, total = build_svg(year, saved)
    (DATA_DIR / f"{year}.svg").write_text(svg, encoding="utf-8")
    years[year] = total
    print(f"{year}: {total} commit contributions")

# GitHub README supports native, clickable HTML details without JavaScript.
sections = ["<!-- COMMITS_START -->",
            "Daily GitHub-recognized **commit contributions** (issues, PRs and reviews excluded).",
            ""]
for year in years:
    open_attr = " open" if year == YEAR else ""
    sections.extend([
        f'<details{open_attr}>',
        f'<summary><strong>{year}</strong> — {years[year]:,} commits</summary>',
        "",
        f'![{year} commit-only contribution calendar](assets/commit-years/{year}.svg)',
        "",
        "</details>",
        "",
    ])
sections.extend([f"_Automatically updated daily (UTC). Last update: {TODAY.isoformat()}._",
                 "<!-- COMMITS_END -->"])
readme_path = Path("README.md")
readme = readme_path.read_text(encoding="utf-8")
begin, end = "<!-- COMMITS_START -->", "<!-- COMMITS_END -->"
if begin not in readme or end not in readme:
    raise ValueError("README commit section markers missing")
readme = readme[:readme.index(begin)] + "\n".join(sections) + readme[readme.index(end) + len(end):]
readme = readme.replace("## 2026 Commit Activity", "## Commit-only Contributions")
readme_path.write_text(readme, encoding="utf-8")
