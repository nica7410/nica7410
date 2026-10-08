#!/usr/bin/env python3
"""Generate a GitHub-style calendar containing only commit contributions."""
import datetime as dt
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

USER = "nica7410"
today = dt.datetime.now(dt.timezone.utc).date()
year = today.year
first = dt.date(year, 1, 1)
days = [first + dt.timedelta(days=i) for i in range((today - first).days + 1)]
counts = {}

# The built-in contributionCalendar also includes issues and PRs.
# Query daily totalCommitContributions instead, in small batches.
for offset in range(0, len(days), 25):
    batch = days[offset:offset + 25]
    aliases = [
        f'd{i}: contributionsCollection(from: "{day}T00:00:00Z", '
        f'to: "{day}T23:59:59Z") {{ totalCommitContributions }}'
        for i, day in enumerate(batch)
    ]
    query = 'query { user(login: "' + USER + '") { ' + ' '.join(aliases) + ' } }'
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": "Bearer " + os.environ["GH_TOKEN"],
            "Content-Type": "application/json",
            "User-Agent": "commit-only-calendar",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise RuntimeError("GraphQL query failed: " + str(payload.get("errors")))
    for i, day in enumerate(batch):
        counts[day] = payload["data"]["user"][f"d{i}"]["totalCommitContributions"]

total = sum(counts.values())
maximum = max(counts.values(), default=0)
# Five GitHub-like levels, including the empty level.
palette = ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")

def level(count):
    if count == 0:
        return 0
    return min(4, 1 + (count * 4 - 1) // max(maximum, 1))

# Sunday is the first row, matching the GitHub calendar.
base = first - dt.timedelta(days=(first.weekday() + 1) % 7)
cell, gap, left, top = 11, 3, 44, 42
step = cell + gap
weeks = ((today - base).days // 7) + 1
width, height = left + weeks * step + 18, 190
rects = []
for day in days:
    column = (day - base).days // 7
    row = (day.weekday() + 1) % 7
    x, y = left + column * step, top + row * step
    number = counts[day]
    rects.append(
        f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
        f'fill="{palette[level(number)]}">'
        f'<title>{day.isoformat()}: {number} commits</title></rect>'
    )
months = []
for month in range(1, 13):
    date = dt.date(year, month, 1)
    if date > today:
        break
    column = (date - base).days // 7
    months.append(
        f'<text x="{left+column*step}" y="33" font-size="11" '
        f'fill="#57606a">{date.strftime("%b")}</text>'
    )
weekdays = [
    f'<text x="7" y="{top+row*step+9}" font-size="10" fill="#57606a">{label}</text>'
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
]
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
    f'viewBox="0 0 {width} {height}" role="img" '
    f'aria-label="{year} commit-only calendar with {total} contributions">'
    f'<text x="{left}" y="17" font-family="Arial,sans-serif" font-size="15" '
    f'font-weight="bold" fill="#24292f">{year}: {total:,} commit contributions</text>'
    + ''.join(months) + ''.join(weekdays) + ''.join(rects) +
    f'<text x="{left}" y="157" font-size="11" fill="#57606a">'
    'Only GitHub-recognized commits; excludes issues, PRs, reviews.'
    '</text></svg>'
)
Path("assets").mkdir(exist_ok=True)
Path("assets/commit-activity.svg").write_text(svg, encoding="utf-8")

path = Path("README.md")
readme = path.read_text(encoding="utf-8")
begin, end = "<!-- COMMITS_START -->", "<!-- COMMITS_END -->"
if begin not in readme or end not in readme:
    raise ValueError("README commit section markers missing")
section = (
    begin + "\n"
    + f"**{year} commit contributions: {total:,}** (updated {today} UTC)\n\n"
    + "![Commit-only contribution calendar](assets/commit-activity.svg)\n"
    + end
)
readme = readme[:readme.index(begin)] + section + readme[readme.index(end)+len(end):]
path.write_text(readme, encoding="utf-8")
print(f"Generated {year} commit-only calendar: {total} commits")
