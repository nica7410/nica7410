#!/usr/bin/env python3
"""Update commit-only stats using GitHub's contributionsCollection API."""
import datetime as dt
import html
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

USER = "nica7410"
today = dt.datetime.now(dt.timezone.utc).date()
year = today.year
start = dt.date(year, 1, 1)
end = min(today + dt.timedelta(days=1), dt.date(year + 1, 1, 1))
windows = []
cursor = start
while cursor < end:
    next_day = min(cursor + dt.timedelta(days=7), end)
    windows.append((cursor, next_day))
    cursor = next_day

# One date-scoped GraphQL collection per week: issues and PRs never enter counts.
parts = [
    f'w{i}: contributionsCollection(from: "{a}T00:00:00Z", '
    f'to: "{b}T00:00:00Z") {{ totalCommitContributions }}'
    for i, (a, b) in enumerate(windows)
]
query = 'query { user(login: "' + USER + '") { ' + ' '.join(parts) + ' } }'
request = Request(
    "https://api.github.com/graphql",
    data=json.dumps({"query": query}).encode(),
    headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Content-Type": "application/json",
        "User-Agent": "profile-commit-only-stats",
    },
)
with urlopen(request, timeout=60) as result:
    response = json.load(result)
if response.get("errors"):
    raise RuntimeError(str(response["errors"]))
data = response["data"]["user"]
counts = [data[f"w{i}"]["totalCommitContributions"] for i in range(len(windows))]
total = sum(counts)

# A compact, static SVG, committed alongside the README.
width, height, left, top, chart_height = 960, 215, 48, 43, 110
chart_width = 850
slot = chart_width / max(len(windows), 1)
maximum = max(counts, default=0) or 1
bars = []
for i, ((a, b), count) in enumerate(zip(windows, counts)):
    h = count / maximum * chart_height
    bars.append(
        f'<rect x="{left+i*slot:.2f}" y="{top+chart_height-h:.2f}" '
        f'width="{max(slot-3, 2):.2f}" height="{h:.2f}" rx="2" fill="#238636">'
        f'<title>{a} - {b-dt.timedelta(days=1)}: {count} commits</title></rect>'
    )
labels = []
for month in range(1, 13):
    day = dt.date(year, month, 1)
    if day >= end:
        break
    x = left + (day - start).days / 7 * slot
    labels.append(
        f'<text x="{x:.1f}" y="174" font-size="12" fill="#57606a">'
        f'{html.escape(day.strftime("%b"))}</text>'
    )
svg = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
    f'viewBox="0 0 {width} {height}" role="img" '
    f'aria-label="{year}: {total} commit contributions">'
    '<rect width="100%" height="100%" fill="white"/>'
    f'<text x="{left}" y="25" font-family="sans-serif" font-size="18" '
    f'fill="#24292f" font-weight="bold">{year} commit contributions: {total:,}</text>'
    f'<line x1="{left}" y1="{top+chart_height}" x2="{left+chart_width}" '
    f'y2="{top+chart_height}" stroke="#d0d7de"/>'
    + ''.join(bars) + ''.join(labels) +
    f'<text x="{left}" y="201" font-size="12" fill="#57606a">'
    'Weekly GitHub-recognized commit contributions; issues and PRs excluded.'
    '</text></svg>'
)
Path("assets").mkdir(exist_ok=True)
Path("assets/commit-activity.svg").write_text(svg, encoding="utf-8")

readme_file = Path("README.md")
readme = readme_file.read_text(encoding="utf-8")
begin, finish = "<!-- COMMITS_START -->", "<!-- COMMITS_END -->"
if begin not in readme or finish not in readme:
    raise ValueError("README is missing commit section markers")
section = (
    begin + "\n"
    + f"**{year} commit contributions: {total:,}** "
      f"(updated {today} UTC)\n\n"
    + "![Commit-only activity](assets/commit-activity.svg)\n"
    + finish
)
readme = readme[:readme.index(begin)] + section + readme[readme.index(finish)+len(finish):]
readme_file.write_text(readme, encoding="utf-8")
print(f"Updated {year} commit-only contributions: {total}")
