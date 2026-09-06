from __future__ import annotations

import pytest

from src.discover_iihf import (
    TournamentNeed,
    configured_event_covers_need,
    extract_tournament_needs,
    resolve_iihf_events,
    schedule_urls_by_event_id,
    title_matches_need,
)
from src.models import Game


def _sihf_game(tournament: str) -> Game:
    return Game(
        id="test",
        date="2026-05-26",
        time="20:20",
        starts_at="2026-05-26T20:20:00+02:00",
        home_team="SUI",
        away_team="FIN",
        venue="Arena",
        tournament=tournament,
    )


def test_extract_tournament_needs_wm_and_olympic() -> None:
    games = [
        _sihf_game("15.05.2026 - 31.05.2026 2026 IIHF Ice Hockey World Championship"),
        _sihf_game("04.02.2026 - 23.02.2026 2026 Olympic Winter Games in Milano"),
    ]
    needs = extract_tournament_needs(games, {})
    assert TournamentNeed(2026, "wm") in needs
    assert TournamentNeed(2026, "olympic") in needs


def test_extract_tournament_needs_redesign_title_with_colon() -> None:
    games = [
        _sihf_game(
            "14.05.2027 - 30.05.2027 IIHF World Championship 2027 "
            "in Düsseldorf & Mannheim / GER"
        ),
        _sihf_game("30.06.2026 - 30.06.2026: Media Day"),
    ]
    needs = extract_tournament_needs(games, {})
    assert needs == {TournamentNeed(2027, "wm")}


def test_configured_event_covers_need_via_kinds() -> None:
    need = TournamentNeed(2026, "olympic")
    event = {"id": 991, "name": "Olympia 2026", "year": 2026, "kinds": ["olympic"]}
    assert configured_event_covers_need(event, need, "2026 Men's Tournament")


def test_title_matches_need() -> None:
    need = TournamentNeed(2026, "wm")
    assert title_matches_need("2026 IIHF Ice Hockey World Championship", need)
    assert not title_matches_need("2025 IIHF Ice Hockey World Championship", need)


def test_resolve_uses_yaml_when_it_covers_needs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_title(event_id: int, user_agent: str) -> str | None:
        calls.append(event_id)
        return {
            969: "2026 IIHF Ice Hockey World Championship",
            991: "2026 Olympic Winter Games",
        }.get(event_id)

    monkeypatch.setattr("src.discover_iihf.fetch_hydra_title", fake_title)

    config = {
        "iihf_events": [
            {
                "id": 969,
                "name": "WM 2026",
                "year": 2026,
                "kinds": ["wm"],
                "hydra_url": "https://stats.iihf.com/Hydra/969/",
                "schedule_url": "https://wm",
            },
            {
                "id": 991,
                "name": "Olympia 2026",
                "year": 2026,
                "kinds": ["olympic"],
                "hydra_url": "https://stats.iihf.com/Hydra/991/",
                "schedule_url": "",
            },
        ],
        "iihf_discovery": {"enabled": True, "id_min": 900, "id_max": 905, "seed_ids": []},
    }
    games = [
        _sihf_game("2026 IIHF Ice Hockey World Championship"),
        _sihf_game("2026 Olympic Winter Games"),
    ]
    events = resolve_iihf_events(config, games, "test")
    assert len(events) == 2
    assert calls == [969, 991]


def test_resolve_discovers_missing_event(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_title(event_id: int, user_agent: str) -> str | None:
        if event_id == 969:
            return "2026 IIHF Ice Hockey World Championship"
        if event_id == 1001:
            return "2027 IIHF Ice Hockey World Championship"
        return None

    monkeypatch.setattr("src.discover_iihf.fetch_hydra_title", fake_title)

    config = {
        "iihf_events": [
            {"id": 969, "name": "WM 2026", "hydra_url": "https://stats.iihf.com/Hydra/969/", "schedule_url": ""},
        ],
        "iihf_discovery": {"enabled": True, "id_min": 1000, "id_max": 1002, "seed_ids": [1001]},
    }
    games = [
        _sihf_game("2026 IIHF Ice Hockey World Championship"),
        _sihf_game("2027 IIHF Ice Hockey World Championship"),
    ]
    events = resolve_iihf_events(config, games, "test")
    assert len(events) == 2
    discovered = [event for event in events if event.get("discovered")]
    assert len(discovered) == 1
    assert discovered[0]["id"] == 1001


def test_schedule_urls_by_event_id_skips_empty() -> None:
    urls = schedule_urls_by_event_id(
        [
            {"id": 1, "schedule_url": "https://example.com/schedule"},
            {"id": 2, "schedule_url": ""},
        ]
    )
    assert urls == {1: "https://example.com/schedule"}
