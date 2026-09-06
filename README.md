# Swiss Hockey Men – ICS-Kalender

Abonnierbarer Kalender mit Spielplan und Resultaten der Schweizer Eishockey-Nationalmannschaft (Herren).

**Kein offizielles Angebot** von SIHF oder IIHF. Daten stammen aus öffentlich zugänglichen Quellen und können sich jederzeit ändern.

## Kalender abonnieren

GitHub Pages (Organisation `codeplay-CH`):

```
https://codeplay-ch.github.io/swiss-hockey-men-schedule/calendar.ics
```

Übersicht: https://codeplay-ch.github.io/swiss-hockey-men-schedule/

Wichtig: Die Root-URL ohne `calendar.ics` liefert keine Kalenderdatei.

### Google Kalender

1. «Andere Kalender» → «Per URL»
2. URL oben einfügen → «Kalender hinzufügen»

### Apple Kalender

1. «Abo hinzufügen …»
2. URL einfügen

Der Kalender wird automatisch aktualisiert, wenn die GitHub Action neue Daten schreibt.

## Datenquellen

| Quelle | Inhalt |
|--------|--------|
| [SIHF Spielplan](https://www.sihf.ch/de/nationalteams/mens-national-team/programm/) | Spielplan (EHT, Olympia, WM-Vorbereitung, WM, …) |
| [IIHF Realtime API](https://realtime.iihf.com/gamestate/GetLatestScoresState/{eventId}) | Live-Resultate (undokumentiert) |
| [IIHF Hydra Stats](https://stats.iihf.com/Hydra/) | Resultate für abgeschlossene IIHF-Spiele |

**Resultate automatisch:** IIHF-Turniere (Olympia `991`, WM `969`).

**Nur Spielplan:** EHT, WM-Vorbereitung, interne Camps (SIHF liefert keine Scores).

## Lokal ausführen

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

`python -m src.main` schreibt lokal `data/games.json` und `public/calendar.ics`. Diese Dateien **nicht** in eigenen Commits mitschicken — die GitHub Action aktualisiert sie alle 30 Minuten.

### Commit-Hygiene

| Wer | Was committen |
|-----|----------------|
| Du | `src/`, `config/`, `tests/`, Workflow, README, … |
| GitHub Action | `data/games.json`, `public/calendar.ics` |

Vor dem Commit (optional, einmalig Hook aktivieren):

```bash
git config core.hooksPath .githooks
```

Der Pre-commit-Hook blockiert `games.json` / `calendar.ics` im Staging. Manuell prüfen: `./scripts/check-commit-hygiene.sh --staged`

Nach lokalem Testlauf Änderungen an den Kalenderdateien verwerfen:

```bash
git restore data/games.json public/calendar.ics
```

Bei Push/PR prüft die Workflow **Commit hygiene**, dass nur der Actions-Bot diese Dateien ändert.

## Entwicklung

Code, Kommentare und Commit-Messages: **Englisch**. Nutzer-sichtbare Texte (Kalender-ICS, Landing Page, README): **Deutsch**.

## Konfiguration

[`config/events.yaml`](config/events.yaml) – SIHF-URL, IIHF-Event-IDs (optional, Override), `iihf_discovery` für automatische Event-ID-Suche, Zeitzone, Camps, `health_check`.

**IIHF Auto-Discovery:** Erkennt an SIHF-Turniernamen (WM, Olympia), welche IIHF-Events nötig sind, und sucht fehlende IDs über Hydra-Seitentitel (`iihf_discovery` in der YAML). Manuelle `iihf_events`-Einträge haben Vorrang; `schedule_url` dort setzt den Link in der ICS-Beschreibung.

Der Build bricht mit Exit-Code 1 ab, wenn SIHF oder der Merge zu wenige Spiele liefern (Standard: jeweils mindestens 10). In der Action-Log erscheinen Zähler pro Quelle.

## Lizenz

MIT (siehe LICENSE, falls vorhanden). Nutzung auf eigene Verantwortung.
