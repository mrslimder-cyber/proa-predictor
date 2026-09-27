"""
scraper/bundesliga_scraper.py

Fuente alternativa de calendario y resultados para la temporada EN CURSO:
la web oficial de la 2. Basketball Bundesliga
(https://www.2basketballbundesliga.de/spielplan/), usada en vez de
Proballers porque el calendario de Proballers viene fallando.

LIMITACIONES (importante leerlas antes de tocar esto):

1. Solo sirve la temporada en curso. El selector de temporada de esa
   página es un widget JS/AJAX -- confirmado en vivo que añadir
   ?saison=2024-2025 a la URL devuelve el mismo HTML que sin parámetro.
   El histórico (config.HISTORICAL_SEASONS) sigue viniendo de Proballers
   (scraper/proballers_scraper.py), este archivo no lo toca.

2. El boxscore NO sale de aquí. El link de cada partido apunta a
   live.2basketballbundesliga.de, que es un widget de liveticker cuyo
   HTML estático viene vacío (los datos se cargan por WebSocket/JS). Por
   eso get_current_season_games() NO devuelve boxscore_url utilizable
   -- eso lo cubre scraper/live_boxscore_scraper.py con un navegador
   headless (Playwright), ver scraper/ingest.py.

3. Sin id de equipo. Esta web no expone un id numérico estable de
   equipo (Proballers sí, vía /equipo/<id>/...). Por eso este scraper
   devuelve NOMBRES de equipo, no ids -- es scraper/ingest.py quien
   resuelve esos nombres contra los ids ya existentes en la BD (o crea
   uno nuevo si es un equipo recién ascendido).

4. Id de partido propio. Tampoco fiamos el Game.id al id del liveticker
   (ese id de hecho ni siquiera aparece en la fila de partidos que
   TODAVÍA no se han jugado -- solo los ya finalizados traen el link
   con "g/<id>"). En vez de eso generamos un id determinista a partir
   de (temporada, fecha, local, visitante), así el mismo partido
   conserva el mismo Game.id la primera vez que aparece como
   "scheduled" y cuando más tarde ya tiene marcador.

Uso:
    from scraper.bundesliga_scraper import get_current_season_games
    games = get_current_season_games()
"""
import re
import time
import zlib
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from config import REQUEST_HEADERS, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT, CURRENT_SEASON

SPIELPLAN_URL = "https://www.2basketballbundesliga.de/spielplan/"

SPIELTAG_RE = re.compile(r"Spieltag\s+(\d+)", re.IGNORECASE)
POKAL_RE = re.compile(r"BBL-?Pokal", re.IGNORECASE)
SCORE_RE = re.compile(r"(\d{1,3})\s*:\s*(\d{1,3})")
DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
LABEL_PREFIX_RE = re.compile(r"^(Datum|Uhrzeit|Heim|Gast|Ergebnis)\s*", re.IGNORECASE)

REQUIRED_COLS = {"Datum", "Uhrzeit", "Heim", "Gast", "Ergebnis"}

# Offset alto para que los ids sintéticos de partido nunca choquen con los
# ids reales de Proballers (que en la práctica se han visto siempre por
# debajo de 1 millón).
GAME_ID_OFFSET = 50_000_000


def _get(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(resp.text, "lxml")


def _clean_cell(text: str) -> str:
    return LABEL_PREFIX_RE.sub("", text.strip()).strip()


def _synthetic_game_id(season: str, date: datetime, home: str, away: str) -> int:
    key = f"{season}|{date.date().isoformat()}|{home.lower()}|{away.lower()}"
    return GAME_ID_OFFSET + (zlib.crc32(key.encode("utf-8")) % 9_000_000)


def get_current_season_games(season: str = CURRENT_SEASON) -> list[dict]:
    """
    Devuelve el calendario de la ronda principal ProA de la temporada en
    curso (jugados y pendientes). Cada dict:
        {game_id, date, matchday, home_team_name, away_team_name,
         home_score, away_score, status, boxscore_url}
    boxscore_url siempre es None (ver limitación 2 en la cabecera).
    """
    soup = _get(SPIELPLAN_URL)

    # La página tiene una segunda sección "BBL-Pokal" más abajo, con sus
    # propios "Spieltag" -- cortamos el documento ahí para no confundir
    # sus tablas con las de la liga regular.
    pokal_heading = soup.find(["h2", "h3", "h4"], string=POKAL_RE)
    if pokal_heading is not None:
        for node in list(pokal_heading.find_all_next()):
            node.decompose()
        pokal_heading.decompose()

    games = []
    seen_ids = set()

    for table in soup.find_all("table"):
        header_cells = {th.get_text(strip=True) for th in table.find_all("th")}
        if not REQUIRED_COLS.issubset(header_cells):
            continue

        matchday = None
        heading = table.find_previous(["h2", "h3", "h4"], string=SPIELTAG_RE)
        if heading:
            m = SPIELTAG_RE.search(heading.get_text())
            if m:
                matchday = int(m.group(1))

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            date_cell, time_cell, home_cell, away_cell, result_cell = cells[:5]

            date_match = DATE_RE.search(_clean_cell(date_cell.get_text(" ", strip=True)))
            if not date_match:
                continue
            day, month, year = (int(x) for x in date_match.groups())
            time_match = TIME_RE.search(_clean_cell(time_cell.get_text(" ", strip=True)))
            hour, minute = (int(x) for x in time_match.groups()) if time_match else (0, 0)
            try:
                game_date = datetime(year, month, day, hour, minute)
            except ValueError:
                continue

            home_name = _clean_cell(home_cell.get_text(" ", strip=True))
            away_name = _clean_cell(away_cell.get_text(" ", strip=True))
            if not home_name or not away_name:
                continue

            result_text = _clean_cell(result_cell.get_text(" ", strip=True))
            score_match = SCORE_RE.search(result_text)
            home_score = int(score_match.group(1)) if score_match else None
            away_score = int(score_match.group(2)) if score_match else None

            game_id = _synthetic_game_id(season, game_date, home_name, away_name)
            if game_id in seen_ids:
                continue
            seen_ids.add(game_id)

            games.append({
                "game_id": game_id,
                "date": game_date,
                "matchday": matchday,
                "home_team_name": home_name,
                "away_team_name": away_name,
                "home_score": home_score,
                "away_score": away_score,
                "status": "final" if home_score is not None else "scheduled",
                "boxscore_url": None,
            })

    return games


if __name__ == "__main__":
    result = get_current_season_games()
    print(f"{len(result)} partidos encontrados.")
    for g in result[:5]:
        print(g)
