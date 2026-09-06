from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

from src.models import Game

SIHF_SCHEDULE_URL = "https://www.sihf.ch/de/nationalteams/mens-national-team/programm/"

DATE_RANGE_PREFIX = re.compile(
    r"^\d{2}\.\d{2}\.\d{4}\s*-\s*\d{2}\.\d{2}\.\d{4}\s*:?\s*"
)

TOURNAMENT_ALIASES: tuple[tuple[str, str], ...] = (
    ("IIHF Ice Hockey World Championship", "WM 2026"),
    ("IIHF World Championship", "WM"),
    ("Olympic Winter Games", "Olympia 2026"),
    ("Euro Hockey Tour", "EHT"),
    ("NOCCO Hockey Games", "EHT"),
    ("SWISS Ice Hockey Games", "Swiss Ice Hockey Games"),
    ("WM-Vorbereitung Week", "WM-Vorbereitung"),
    ("Fortuna Hockey Games", "Fortuna Hockey Games"),
    ("Beijer Hockey Games", "Beijer Hockey Games"),
    ("Prospect Camp", "Prospect Camp"),
    ("Media Day", "Media Day"),
)


def _tournament_label(tournament: str) -> str:
    name = DATE_RANGE_PREFIX.sub("", tournament).strip()
    for needle, label in TOURNAMENT_ALIASES:
        if needle in name:
            return label
    if len(name) > 42:
        return f"{name[:39]}…"
    return name


def _format_summary(game: Game) -> str:
    matchup = f"{game.home_team} – {game.away_team}"
    if game.score_home is not None and game.score_away is not None:
        matchup = f"{matchup} ({game.score_home}:{game.score_away})"
    return f"{_tournament_label(game.tournament)} · {matchup}"


def _format_description(
    game: Game,
    iihf_schedule_urls: dict[int, str] | None = None,
) -> str:
    lines = [
        f"Turnier: {game.tournament}",
        f"Ort: {game.venue}",
        f"Status: {game.status}",
        f"SIHF: {SIHF_SCHEDULE_URL}",
    ]
    if game.iihf_event_id and iihf_schedule_urls:
        schedule_url = iihf_schedule_urls.get(game.iihf_event_id, "").strip()
        if schedule_url:
            lines.append(f"IIHF: {schedule_url}")
    return "\n".join(lines)


def build_calendar(
    games: list[Game],
    calendar_name: str,
    tz_name: str,
    iihf_schedule_urls: dict[int, str] | None = None,
) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//iihf-swiss-hockey-men-schedule//NONSGML//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("name", calendar_name)
    cal.add("x-wr-calname", calendar_name)
    cal.add("x-wr-timezone", tz_name)

    local_tz = ZoneInfo(tz_name)
    utc = ZoneInfo("UTC")
    now = datetime.now(utc)

    for game in games:
        starts = datetime.fromisoformat(game.starts_at)
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=local_tz)
        starts_utc = starts.astimezone(utc)
        ends_utc = starts_utc + timedelta(hours=3)

        event = Event()
        event.add("uid", f"{game.id}@iihf-swiss-hockey-men-schedule")
        event.add("dtstamp", now)
        event.add("dtstart", starts_utc)
        event.add("dtend", ends_utc)
        event.add("summary", _format_summary(game))
        event.add("description", _format_description(game, iihf_schedule_urls))
        event.add("location", game.venue)
        cal.add_component(event)

    return cal.to_ical()


def write_ics(
    games: list[Game],
    output_path: Path,
    calendar_name: str,
    tz_name: str,
    iihf_schedule_urls: dict[int, str] | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        build_calendar(games, calendar_name, tz_name, iihf_schedule_urls)
    )
