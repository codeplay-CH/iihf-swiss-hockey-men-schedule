from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from zoneinfo import ZoneInfo

import httpx

from src.models import Game
from src.teams import normalize_team_code, parse_matchup

DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
SECTION_HEADING_RE = re.compile(r"<h[34][^>]*>", re.IGNORECASE)
SECTION_TITLE_RE = re.compile(r"(.*?)</h[34]>", re.IGNORECASE | re.DOTALL)


def _make_game_id(date_iso: str, home: str, away: str, tournament: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", tournament.lower()).strip("-")[:40]
    return f"sihf-{date_iso}-{home}-{away}-{slug}"


def _parse_local_datetime(date_iso: str, time_hm: str, tz_name: str) -> datetime:
    year, month, day = map(int, date_iso.split("-"))
    hour, minute = map(int, time_hm.split(":"))
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(tz_name))


def _iter_schedule_sections(html: str) -> list[tuple[str, str]]:
    """Split SIHF HTML into (tournament, body) pairs.

    The old site used ``<h4>`` section titles. The 2026 redesign uses ``<h3>``
    and sometimes inserts an empty ``<h3>`` inside the table wrapper; empty
    headings inherit the previous tournament so their rows stay attached.
    """
    sections: list[tuple[str, str]] = []
    for part in SECTION_HEADING_RE.split(html)[1:]:
        title_match = SECTION_TITLE_RE.match(part)
        if not title_match:
            continue

        tournament = unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip()
        tournament = re.sub(r"\s+", " ", tournament)
        body = part[title_match.end() :]

        if not tournament:
            if sections:
                prev_title, prev_body = sections[-1]
                sections[-1] = (prev_title, prev_body + body)
            continue

        sections.append((tournament, body))

    return sections


def fetch_sihf_schedule(
    url: str,
    user_agent: str,
    tz_name: str,
    include_camps: bool = True,
) -> list[Game]:
    headers = {"User-Agent": user_agent}
    try:
        response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"WARNING: SIHF schedule fetch failed ({exc}); using empty live result")
        return []

    games: list[Game] = []
    for tournament, body in _iter_schedule_sections(response.text):
        if not include_camps and (
            "prospect camp" in tournament.lower() or "media day" in tournament.lower()
        ):
            continue

        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.IGNORECASE | re.DOTALL):
            cells = [
                unescape(re.sub(r"<[^>]+>", "", cell)).strip()
                for cell in re.findall(
                    r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL
                )
            ]
            if len(cells) < 4:
                continue

            date_raw, time_raw, matchup_raw, venue = cells[0], cells[1], cells[2], cells[3]
            date_match = DATE_RE.match(date_raw)
            time_match = TIME_RE.match(time_raw)
            if not date_match or not time_match:
                continue

            matchup = parse_matchup(matchup_raw)
            if not matchup:
                continue

            home, away = matchup
            day, month, year = date_match.groups()
            date_iso = f"{year}-{month}-{day}"
            time_hm = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
            starts_at = _parse_local_datetime(date_iso, time_hm, tz_name).isoformat()

            games.append(
                Game(
                    id=_make_game_id(date_iso, home, away, tournament),
                    date=date_iso,
                    time=time_hm,
                    starts_at=starts_at,
                    home_team=home,
                    away_team=away,
                    venue=venue,
                    tournament=tournament,
                    source="sihf",
                )
            )

    return games
