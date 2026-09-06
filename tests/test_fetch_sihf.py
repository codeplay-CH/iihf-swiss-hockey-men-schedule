from __future__ import annotations

import httpx
import pytest

from src.fetch_sihf import fetch_sihf_schedule

SIHF_HTML_FIXTURE = """
<html><body>
<h4>15.05.2026 - 31.05.2026 IIHF Ice Hockey World Championship</h4>
<table>
<tr>
  <td>26.05.2026</td>
  <td>20:20</td>
  <td>SUI - FIN</td>
  <td>Swiss Life Arena, Zurich, SUI</td>
</tr>
</table>
<h4>01.01.2026 Prospect Camp</h4>
<table>
<tr>
  <td>02.01.2026</td>
  <td>10:00</td>
  <td>SUI - FIN</td>
  <td>Camp</td>
</tr>
</table>
</body></html>
"""


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


def test_fetch_sihf_parses_table_row(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(SIHF_HTML_FIXTURE)

    monkeypatch.setattr(httpx, "get", fake_get)

    games = fetch_sihf_schedule(
        "https://example.test/schedule",
        user_agent="test",
        tz_name="Europe/Zurich",
        include_camps=False,
    )

    assert len(games) == 1
    game = games[0]
    assert game.home_team == "SUI"
    assert game.away_team == "FIN"
    assert game.date == "2026-05-26"
    assert game.time == "20:20"
    assert game.venue == "Swiss Life Arena, Zurich, SUI"


SIHF_REDESIGN_HTML_FIXTURE = """
<html><body>
<h3>27.07.2026 - 31.07.2026: Prospect Camp in Davos</h3>
<details>
<summary>Prospect Camp</summary>
<div class="c-table__wrapper">
<h3 class="h3 mb-m"></h3>
<table>
<tr>
  <td>30.07.2026</td>
  <td>16:30</td>
  <td>SUI Red - SUI White</td>
  <td>Davos</td>
</tr>
</table>
</div>
</details>
<h3>02.11.2026 - 09.11.2026: NOCCO Hockey Games in Helsinki / FIN</h3>
<div class="c-table__wrapper">
<h3 class="h3 mb-m"></h3>
<table>
<tr>
  <td>05.11.2026</td>
  <td>17:30</td>
  <td>SUI - FIN</td>
  <td>Veikkaus Arena, Helsinki</td>
</tr>
</table>
</div>
</body></html>
"""


def test_fetch_sihf_skips_camps_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(SIHF_HTML_FIXTURE)

    monkeypatch.setattr(httpx, "get", fake_get)

    games = fetch_sihf_schedule(
        "https://example.test/schedule",
        user_agent="test",
        tz_name="Europe/Zurich",
        include_camps=False,
    )
    assert all("prospect camp" not in g.tournament.lower() for g in games)


def test_fetch_sihf_parses_redesign_h3_and_empty_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, **kwargs: object) -> _FakeResponse:
        return _FakeResponse(SIHF_REDESIGN_HTML_FIXTURE)

    monkeypatch.setattr(httpx, "get", fake_get)

    games = fetch_sihf_schedule(
        "https://example.test/programm",
        user_agent="test",
        tz_name="Europe/Zurich",
        include_camps=True,
    )

    assert len(games) == 2
    camp, eht = games
    assert camp.date == "2026-07-30"
    assert camp.home_team == "SUI RED"
    assert camp.away_team == "SUI WHITE"
    assert "Prospect Camp" in camp.tournament
    assert eht.date == "2026-11-05"
    assert eht.home_team == "SUI"
    assert eht.away_team == "FIN"
    assert eht.venue == "Veikkaus Arena, Helsinki"
    assert "NOCCO Hockey Games" in eht.tournament


def test_fetch_sihf_returns_empty_on_http_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    request = httpx.Request("GET", "https://example.test/missing")
    response = httpx.Response(404, request=request)

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        return response

    monkeypatch.setattr(httpx, "get", fake_get)

    games = fetch_sihf_schedule(
        "https://example.test/missing",
        user_agent="test",
        tz_name="Europe/Zurich",
    )

    assert games == []
    assert "WARNING: SIHF schedule fetch failed" in capsys.readouterr().out
