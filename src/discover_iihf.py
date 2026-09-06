from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from src.models import Game

HYDRA_BASE = "https://stats.iihf.com/Hydra"
TITLE_RE = re.compile(r"<title>\s*([^<]+?)\s*</title>", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(20\d{2})\b")
DATE_RANGE_PREFIX = re.compile(
    r"^\d{2}\.\d{2}\.\d{4}\s*-\s*\d{2}\.\d{2}\.\d{4}\s*:?\s*"
)

DEFAULT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("IIHF Ice Hockey World Championship", "wm"),
    ("IIHF World Championship", "wm"),
    ("Olympic Winter Games", "olympic"),
)


@dataclass(frozen=True)
class TournamentNeed:
    year: int
    kind: str


def _tournament_patterns(discovery_cfg: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw = discovery_cfg.get("tournament_patterns")
    if not raw:
        return DEFAULT_PATTERNS
    return tuple((item["needle"], item["kind"]) for item in raw)


def _normalize_tournament_name(tournament: str) -> str:
    return DATE_RANGE_PREFIX.sub("", tournament).strip()


def extract_tournament_needs(
    sihf_games: list[Game],
    discovery_cfg: dict[str, Any],
) -> set[TournamentNeed]:
    needs: set[TournamentNeed] = set()
    patterns = _tournament_patterns(discovery_cfg)

    for game in sihf_games:
        if not game.involves_sui():
            continue
        name = _normalize_tournament_name(game.tournament)
        year_match = YEAR_RE.search(name)
        if not year_match:
            continue
        year = int(year_match.group(1))
        for needle, kind in patterns:
            if needle in name:
                needs.add(TournamentNeed(year=year, kind=kind))
                break

    return needs


def extract_year(text: str) -> int | None:
    match = YEAR_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def configured_event_covers_need(
    event: dict[str, Any],
    need: TournamentNeed,
    title: str | None,
) -> bool:
    if title and title_matches_need(title, need):
        return True
    kinds = event.get("kinds") or []
    if need.kind not in kinds:
        return False
    event_year = event.get("year")
    if event_year is None:
        event_year = extract_year(str(event.get("name", "")))
    return event_year == need.year


def title_matches_need(title: str, need: TournamentNeed) -> bool:
    year = extract_year(title)
    if year != need.year:
        return False
    lower = title.lower()
    if need.kind == "wm":
        return "world championship" in lower
    if need.kind == "olympic":
        return "olympic" in lower
    return False


def fetch_hydra_title(event_id: int, user_agent: str) -> str | None:
    url = f"{HYDRA_BASE}/{event_id}/"
    headers = {"User-Agent": user_agent}
    try:
        response = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            return None
        match = TITLE_RE.search(response.text)
        if not match:
            return None
        return re.sub(r"\s+", " ", match.group(1)).strip()
    except httpx.HTTPError:
        return None


def _short_name(title: str, need: TournamentNeed) -> str:
    year = need.year
    if need.kind == "wm":
        return f"WM {year}"
    if need.kind == "olympic":
        return f"Olympics {year}"
    return title[:48]


def _event_dict(event_id: int, title: str, need: TournamentNeed) -> dict[str, Any]:
    return {
        "id": event_id,
        "name": _short_name(title, need),
        "hydra_url": f"{HYDRA_BASE}/{event_id}/",
        "schedule_url": "",
        "discovered": True,
        "hydra_title": title,
    }


def _scan_ids(discovery_cfg: dict[str, Any]) -> list[int]:
    seed_ids = [int(value) for value in discovery_cfg.get("seed_ids", [])]
    id_min = int(discovery_cfg.get("id_min", 900))
    id_max = int(discovery_cfg.get("id_max", 1050))
    ordered: list[int] = []
    seen: set[int] = set()
    for event_id in seed_ids + list(range(id_min, id_max + 1)):
        if event_id in seen:
            continue
        seen.add(event_id)
        ordered.append(event_id)
    return ordered


def resolve_iihf_events(
    config: dict[str, Any],
    sihf_games: list[Game],
    user_agent: str,
) -> list[dict[str, Any]]:
    configured = [dict(event) for event in config.get("iihf_events", [])]
    discovery_cfg = config.get("iihf_discovery") or {}
    if not discovery_cfg.get("enabled", False):
        return configured

    needs = extract_tournament_needs(sihf_games, discovery_cfg)
    if not needs:
        return configured

    configured_ids = {int(event["id"]) for event in configured}
    title_cache: dict[int, str | None] = {}
    unsatisfied: set[TournamentNeed] = set()

    def cached_title(event_id: int) -> str | None:
        if event_id not in title_cache:
            title_cache[event_id] = fetch_hydra_title(event_id, user_agent)
        return title_cache[event_id]

    for need in needs:
        covered = False
        for event in configured:
            title = cached_title(int(event["id"]))
            if configured_event_covers_need(event, need, title):
                covered = True
                break
        if not covered:
            unsatisfied.add(need)

    if not unsatisfied:
        return configured

    discovered: list[dict[str, Any]] = []
    discovered_ids: set[int] = set()

    for event_id in _scan_ids(discovery_cfg):
        if event_id in configured_ids or event_id in discovered_ids:
            continue
        title = cached_title(event_id)
        if not title:
            continue
        matched = [need for need in unsatisfied if title_matches_need(title, need)]
        if not matched:
            continue
        for need in matched:
            unsatisfied.discard(need)
        discovered.append(_event_dict(event_id, title, matched[0]))
        discovered_ids.add(event_id)
        if not unsatisfied:
            break

    if unsatisfied:
        labels = ", ".join(f"{need.kind}/{need.year}" for need in sorted(unsatisfied))
        print(f"WARNING: Could not discover IIHF events for: {labels}")

    return configured + discovered


def schedule_urls_by_event_id(events: list[dict[str, Any]]) -> dict[int, str]:
    urls: dict[int, str] = {}
    for event in events:
        schedule_url = (event.get("schedule_url") or "").strip()
        if schedule_url:
            urls[int(event["id"])] = schedule_url
    return urls
