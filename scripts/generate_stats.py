#!/usr/bin/env python3
"""
Generates stats.svg, streak.svg, langs.svg, year.svg from the GitHub GraphQL API.
Standard library only (urllib) -- no dependencies to break in CI.

Env vars required:
  GITHUB_TOKEN  - provided automatically by Actions
  GH_LOGIN      - repository_owner, i.e. your username
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["GITHUB_TOKEN"]
LOGIN = os.environ["GH_LOGIN"]
API_URL = "https://api.github.com/graphql"

# ---- pinned whole-UTC-day window (see guide: avoids nightly no-op-looking drift) ----
now = datetime.now(timezone.utc)
TO = now.replace(hour=23, minute=59, second=59, microsecond=0)
FROM = (TO - timedelta(days=364)).replace(hour=0, minute=0, second=0, microsecond=0)

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      nodes {
        name
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def gh_graphql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": LOGIN,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        print(payload["errors"], file=sys.stderr)
        raise SystemExit(1)
    return payload["data"]


def fetch():
    variables = {
        "login": LOGIN,
        "from": FROM.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": TO.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return gh_graphql(QUERY, variables)


# ---------------------------------------------------------------------------
# shared visual language -- same ramp/typeface as the portrait, minimal ink
# ---------------------------------------------------------------------------
RAMP = " .`:-=+*cs#%@"
INK = "#1a1a1a"
DIM = "#8a8a8a"
FONT_FAMILY = "'jbm-body', monospace"

FONT_CSS = ""  # injected by inject_font() from assets/fonts/body.woff2


def inject_font():
    global FONT_CSS
    path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "body.woff2")
    if not os.path.exists(path):
        FONT_CSS = ""
        return
    import base64
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    FONT_CSS = f"""
@font-face {{
  font-family: 'jbm-body';
  src: url(data:font/woff2;base64,{b64}) format('woff2');
}}
"""


def svg_wrap(width, height, body):
    return f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
<defs><style>
{FONT_CSS}
text {{ font-family: {FONT_FAMILY}; fill: {INK}; }}
.dim {{ fill: {DIM}; }}
</style></defs>
<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>
{body}
</svg>'''


# ---------------------------------------------------------------------------
# stats.svg -- hero total + weekly sparkline (columns, not a line -- see guide)
# ---------------------------------------------------------------------------
def build_stats_svg(data):
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    total = cal["totalContributions"]
    weeks = cal["weeks"]
    weekly_counts = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks]

    W, H = 480, 160
    pad = 20
    chart_w = W - pad * 2
    chart_h = 70
    chart_top = 70
    n = len(weekly_counts)
    bar_w = chart_w / n * 0.7
    gap = chart_w / n
    maxv = max(weekly_counts) or 1

    bars = []
    for i, v in enumerate(weekly_counts):
        bh = (v / maxv) * chart_h
        x = pad + i * gap
        y = chart_top + chart_h - bh
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{INK}"/>')

    body = f'''
<text x="{pad}" y="40" font-size="34">{total:,}</text>
<text x="{pad}" y="58" font-size="12" class="dim">contributions in the last year</text>
{''.join(bars)}
'''
    return svg_wrap(W, H, body)


# ---------------------------------------------------------------------------
# streak.svg -- current + longest streak with date ranges
# ---------------------------------------------------------------------------
def build_streak_svg(data):
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for w in cal["weeks"]:
        for d in w["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    days.sort()

    longest = cur = 0
    longest_range = cur_range = None
    run_start = None
    for date, count in days:
        if count > 0:
            if run_start is None:
                run_start = date
            cur += 1
            if cur > longest:
                longest = cur
                longest_range = (run_start, date)
        else:
            run_start = None
            cur = 0

    # current streak = trailing run ending on the last day with contributions
    cur = 0
    cur_end = None
    for date, count in reversed(days):
        if count > 0:
            if cur == 0:
                cur_end = date
            cur += 1
        else:
            break
    cur_start = None
    if cur > 0:
        idx = [d for d, _ in days].index(cur_end)
        cur_start = days[idx - cur + 1][0]
        cur_range = (cur_start, cur_end)
    else:
        cur_range = None

    W, H = 480, 140
    def fmt(r):
        return f"{r[0]} \u2192 {r[1]}" if r else "\u2014"

    body = f'''
<text x="20" y="40" font-size="30">{cur}</text>
<text x="20" y="58" font-size="12" class="dim">current streak</text>
<text x="20" y="74" font-size="11" class="dim">{fmt(cur_range)}</text>

<text x="260" y="40" font-size="30">{longest}</text>
<text x="260" y="58" font-size="12" class="dim">longest streak</text>
<text x="260" y="74" font-size="11" class="dim">{fmt(longest_range)}</text>
'''
    return svg_wrap(W, H, body)


# ---------------------------------------------------------------------------
# langs.svg -- top languages by bytes across public, non-fork repos
# ---------------------------------------------------------------------------
def build_langs_svg(data):
    totals = {}
    colors = {}
    for repo in data["user"]["repositories"]["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or INK

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:6]
    grand_total = sum(v for _, v in ranked) or 1

    W, H = 480, 30 + 24 * len(ranked)
    rows = []
    for i, (name, size) in enumerate(ranked):
        pct = size / grand_total * 100
        y = 30 + i * 24
        bar_max = 220
        bar_w = bar_max * (size / ranked[0][1])
        rows.append(f'''
<text x="20" y="{y}" font-size="13">{name}</text>
<rect x="160" y="{y-10}" width="{bar_max}" height="10" fill="#eeeeee"/>
<rect x="160" y="{y-10}" width="{bar_w:.1f}" height="10" fill="{colors.get(name, INK)}"/>
<text x="390" y="{y}" font-size="12" class="dim">{pct:.1f}%</text>''')

    body = f'<text x="20" y="18" font-size="12" class="dim">top languages, by bytes</text>' + "".join(rows)
    return svg_wrap(W, H, body)


# ---------------------------------------------------------------------------
# year.svg -- one character per day, using the portrait's own ramp
# ---------------------------------------------------------------------------
def build_year_svg(data):
    cal = data["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    all_counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    maxv = max(all_counts) or 1

    CHAR_W, CHAR_H = 12, 14
    n_weeks = len(weeks)
    W = 20 + n_weeks * CHAR_W
    H = 20 + 7 * CHAR_H

    cells = []
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            count = d["contributionCount"]
            idx = 0 if count == 0 else min(len(RAMP) - 1, 1 + int((count / maxv) * (len(RAMP) - 2)))
            ch = RAMP[idx]
            if ch == " ":
                continue
            dow = datetime.strptime(d["date"], "%Y-%m-%d").weekday()  # Mon=0
            dow = (dow + 1) % 7  # convert to Sun=0 to match GitHub's calendar layout
            x = 10 + wi * CHAR_W
            y = 14 + dow * CHAR_H
            esc = ch.replace("&", "&amp;").replace("<", "&lt;")
            cells.append(f'<text x="{x}" y="{y}" font-size="12">{esc}</text>')

    body = "".join(cells)
    return svg_wrap(W, H, body)


def write_if_changed(path, content):
    if os.path.exists(path):
        with open(path) as f:
            if f.read() == content:
                return False
    with open(path, "w") as f:
        f.write(content)
    return True


def main():
    inject_font()
    data = fetch()
    out_dir = os.path.join(os.path.dirname(__file__), "..")
    write_if_changed(os.path.join(out_dir, "stats.svg"), build_stats_svg(data))
    write_if_changed(os.path.join(out_dir, "streak.svg"), build_streak_svg(data))
    write_if_changed(os.path.join(out_dir, "langs.svg"), build_langs_svg(data))
    write_if_changed(os.path.join(out_dir, "year.svg"), build_year_svg(data))


if __name__ == "__main__":
    main()
