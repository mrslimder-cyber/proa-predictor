"""
scraper/realgm_scraper.py

Fuente UNICA (historico + temporada en curso) para la Pro A alemana,
usando RealGM (https://basketball.realgm.com/international/league/94/German-Pro-A)
en vez de:
  - Proballers (scraper/proballers_scraper.py, ahora eliminado): empezo a
    devolver 403 Forbidden en TODAS las temporadas historicas.
  - 2basketballbundesliga.de (scraper/bundesliga_scraper.py +
    scraper/live_boxscore_scraper.py, ambos eliminados): el widget en
    vivo no conserva datos una vez el partido termina (confirmado: 0/7
    boxscores recuperados tras varias ejecuciones reales).

Por que RealGM sirve para TODO a la vez:
  - Boxscore final completo por partido (equipo + jugador), e incluye
    las Four Factors YA CALCULADAS (eFG%, TO%, OR%, FTR) -- ya no hace
    falta calcularlas a mano como hacia proballers_scraper._team_four_factors.
  - El id numerico de cada partido es ESTABLE entre su estado "preview"
    (antes de jugarse) y "boxscore" (ya jugado): el MISMO id aparece en
    ambas URLs, p.ej. .../preview/2026-09-26/.../525443 y
    .../boxscore/2026-09-26/.../525443. Esto es justo lo que faltaba en
    bundesliga_scraper.py (generaba un id distinto por hash del nombre
    de equipo, que cambiaba entre ejecuciones y duplicaba partidos).
  - Los equipos tambien tienen un id numerico propio y estable
    (/international/league/94/German-Pro-A/team/<id>/<slug>), asi que
    tampoco hace falta el emparejamiento por nombre normalizado que
    usaba _resolve_team_ids_by_name() en el ingest.py anterior.

IMPORTANTE -- sin verificar en produccion contra cientos de partidos
reales, revisalo en tu primera ejecucion (mismo espiritu que los avisos
que ya tenia proballers_scraper.py con sus propios patrones de URL):

  1. Rango de fechas por temporada (SEASON_START_MONTH_DAY /
     SEASON_END_MONTH_DAY mas abajo): aproximado a "1 sep - 30 jun" para
     cubrir regular season + playoffs. Si tu temporada real empieza o
     termina en fechas muy distintas, ajusta esas dos constantes.
  2. Se asume que en cada bloque de partido el PRIMER link de equipo es
     el LOCAL y el segundo el VISITANTE (asi aparece en el titulo del
     boxscore, p.ej. "HARKO Merlins Crailsheim 81, ETB Miners Essen 67"
     con HARKO de local) -- confirmado en un boxscore real concreto, no
     en una muestra grande.
  3. _find_team_totals_row() identifica la fila de totales de un equipo
     dentro de su tabla de jugadores por tener "Min" >= 200 (duracion
     reglamentaria de un partido; cada prorroga suma 25 min mas). Si ves
     el aviso "[WARN] no se encontro la fila de totales..." con
     frecuencia, es la primera sospechosa a revisar.
  4. pandas.read_html() puede comportarse de forma sorprendente con
     tablas de cabecera doble (como "Four Factors"); si cambia el
     layout de RealGM, los dicts de salida pueden venir con campos a
     None en vez de lanzar una excepcion clara -- por eso cada campo se
     parsea de forma defensiva (_safe_int/_safe_float/etc devuelven
     None en vez de reventar).

Uso:
    from scraper.realgm_scraper import get_season_games, get_boxscore
    games = get_season_games("2025-2026")
    finished = [g for g in games if g["boxscore_url"]]
    box = get_boxscore(finished[0]["boxscore_url"])
"""
import io
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import REALGM_LEAGUE_ID, REALGM_LEAGUE_URL, REQUEST_HEADERS, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT

TEAM_HREF_RE = re.compile(
    rf"/international/league/{REALGM_LEAGUE_ID}/German-Pro-A/team/(\d+)/([^/\"]+)"
)
# Cubre tanto partidos aun no jugados (.../preview/...) como ya
# finalizados con boxscore publicado (.../boxscore/...) -- el id
# numerico final del href es el MISMO en ambos casos para un mismo
# partido, ver nota de cabecera.
GAME_HREF_RE = re.compile(
    r"/international/(preview|boxscore)/(\d{4}-\d{2}-\d{2})/([^/\"]+)/(\d+)"
)

# Ver aviso 1 de la cabecera del modulo.
SEASON_START_MONTH_DAY = (9, 1)
SEASON_END_MONTH_DAY = (6, 30)

_FOUR_FACTORS_COLS = {"eFG%", "TO%", "OR%", "FTR"}
_PLAYER_COLS = {"Min", "FGM-A", "3PM-A", "FTM-A", "PTS"}
_FINAL_SCORE_COL = "Final"


def _get(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(resp.text, "lxml")


def _season_date_range(season: str) -> tuple[datetime, datetime]:
    start_year = int(season.split("-")[0])
    end_year = start_year + 1
    start = datetime(start_year, *SEASON_START_MONTH_DAY)
    end = datetime(end_year, *SEASON_END_MONTH_DAY)
    return start, end


def _find_game_block(link):
    """Sube por los ancestros del link de partido hasta el contenedor
    MINIMO que ya incluye los 2 links de equipo de ESE partido (mismo
    enfoque que usaba proballers_scraper._find_game_block: parar en
    cuanto haya exactamente 1 link de partido y 2+ de equipo evita subir
    hasta un contenedor que mezcle varios partidos del mismo dia)."""
    node = link.parent
    while node is not None:
        team_links = node.find_all("a", href=TEAM_HREF_RE)
        game_links = node.find_all("a", href=GAME_HREF_RE)
        if len(team_links) >= 2 and len(game_links) == 1:
            return node
        node = node.parent
    return None


def get_games_for_date(date: datetime) -> list[dict]:
    """
    Partidos de UN dia concreto. Devuelve, por partido:
        {game_id, date, home_team_id, home_team_name, away_team_id,
         away_team_name, status, boxscore_url}
    status es "final" si RealGM ya publico el boxscore detallado de ese
    partido, "scheduled" en caso contrario -- esto incluye partidos que
    ya se jugaron pero cuyo boxscore RealGM aun no proceso (se ve en la
    propia web como resultado con marcador pero sin link "Box Score"
    todavia); ese caso se reintentara solo con volver a correr el
    pipeline mas adelante.
    """
    date_str = date.strftime("%Y-%m-%d")
    url = f"{REALGM_LEAGUE_URL}/scores/{date_str}/{REALGM_LEAGUE_ID}"
    soup = _get(url)

    games = []
    seen_ids = set()
    for link in soup.find_all("a", href=GAME_HREF_RE):
        m = GAME_HREF_RE.search(link["href"])
        if not m:
            continue
        kind, link_date, _slug, game_id = m.groups()
        game_id = int(game_id)
        if game_id in seen_ids:
            continue

        block = _find_game_block(link)
        if block is None:
            continue
        team_links = block.find_all("a", href=TEAM_HREF_RE)
        if len(team_links) < 2:
            continue
        home_m = TEAM_HREF_RE.search(team_links[0]["href"])
        away_m = TEAM_HREF_RE.search(team_links[1]["href"])
        if not home_m or not away_m:
            continue
        seen_ids.add(game_id)

        full_url = (
            f"https://basketball.realgm.com{link['href']}"
            if link["href"].startswith("/")
            else link["href"]
        )
        games.append({
            "game_id": game_id,
            "date": datetime.strptime(link_date, "%Y-%m-%d"),
            "home_team_id": int(home_m.group(1)),
            "home_team_name": home_m.group(2).replace("-", " "),
            "away_team_id": int(away_m.group(1)),
            "away_team_name": away_m.group(2).replace("-", " "),
            "status": "final" if kind == "boxscore" else "scheduled",
            "boxscore_url": full_url if kind == "boxscore" else None,
        })
    return games


def get_season_games(season: str) -> list[dict]:
    """
    Recorre dia a dia el rango aproximado de la temporada (ver
    _season_date_range / aviso 1 de cabecera) y agrega todos los
    partidos encontrados. Es la forma mas robusta de listar la
    temporada completa sin depender de un endpoint de calendario no
    verificado. Caro la primera vez (un request por dia); barato
    despues porque scraper/ingest.py es idempotente (only_new=True).
    """
    start, end = _season_date_range(season)
    all_games: dict[int, dict] = {}
    day = start
    while day <= end:
        try:
            for g in get_games_for_date(day):
                all_games[g["game_id"]] = g  # la vista mas reciente gana (p.ej. pasa a "final")
        except Exception as e:
            print(f"  [WARN] fallo consultando RealGM del {day.date()}: {e}")
        day += timedelta(days=1)
    return sorted(all_games.values(), key=lambda g: g["date"])


def _parse_made_att(val) -> tuple[int | None, int | None]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None, None
    m = re.match(r"(\d+)\s*-\s*(\d+)", str(val))
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _find_team_totals_row(player_table: pd.DataFrame):
    """Ver aviso 3 de la cabecera del modulo."""
    for _, row in player_table[::-1].iterrows():
        min_val = str(row.get("Min", "")).strip()
        if min_val.isdigit() and int(min_val) >= 200:
            return row
    return None


def get_boxscore(boxscore_url: str) -> dict:
    """
    Descarga y parsea el boxscore completo de un partido ya finalizado:
        {
          "home_score": int|None, "away_score": int|None,
          "team_stats": [ {team_id, is_home, pts, ..., efg_pct, tov_pct, orb_pct, ft_rate}, x2 ],
          "player_stats": [ {team_id, player_name, pts, ..., minutes, valuation}, ... ],
        }
    Si alguna parte no se encuentra (cambio de maquetacion de RealGM),
    esa parte vuelve vacia/None en vez de lanzar excepcion -- es
    scraper/ingest.py quien decide reintentar en la siguiente ejecucion.
    """
    soup = _get(boxscore_url)
    tables = pd.read_html(io.StringIO(str(soup)))

    team_links = soup.find_all("a", href=TEAM_HREF_RE)
    team_order = []
    for link in team_links:
        m = TEAM_HREF_RE.search(link["href"])
        if m:
            info = (int(m.group(1)), m.group(2).replace("-", " "))
            if info not in team_order:
                team_order.append(info)
    team_order = team_order[:2]  # local, visitante

    home_score = away_score = None
    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        if cols and cols[-1] == _FINAL_SCORE_COL and len(t) == 2:
            home_score = _safe_int(t.iloc[0][_FINAL_SCORE_COL])
            away_score = _safe_int(t.iloc[1][_FINAL_SCORE_COL])
            break

    four_factors: dict[int, dict] = {}
    for t in tables:
        cols = {str(c).strip() for c in t.columns}
        if _FOUR_FACTORS_COLS.issubset(cols) and len(t) == 2:
            for i, (team_id, _name) in enumerate(team_order[: len(t)]):
                row = t.iloc[i]
                four_factors[team_id] = {
                    "efg_pct": _safe_float(row.get("eFG%")),
                    "tov_pct": _safe_float(row.get("TO%")),
                    "orb_pct": _safe_float(row.get("OR%")),
                    "ft_rate": _safe_float(row.get("FTR")),
                }
            break

    player_tables = [
        t for t in tables if _PLAYER_COLS.issubset({str(c).strip() for c in t.columns})
    ]

    team_stats = []
    player_stats = []
    for i, (team_id, _name) in enumerate(team_order):
        if i >= len(player_tables):
            break
        pt = player_tables[i]

        totals_row = _find_team_totals_row(pt)
        if totals_row is not None:
            fgm, fga = _parse_made_att(totals_row.get("FGM-A"))
            fg3m, fg3a = _parse_made_att(totals_row.get("3PM-A"))
            ftm, fta = _parse_made_att(totals_row.get("FTM-A"))
            ts = {
                "team_id": team_id,
                "is_home": (i == 0),
                "fg2_made": (fgm - fg3m) if fgm is not None and fg3m is not None else None,
                "fg2_att": (fga - fg3a) if fga is not None and fg3a is not None else None,
                "fg3_made": fg3m,
                "fg3_att": fg3a,
                "ft_made": ftm,
                "ft_att": fta,
                "oreb": _safe_int(totals_row.get("Off")),
                "dreb": _safe_int(totals_row.get("Def")),
                "reb": _safe_int(totals_row.get("Reb")),
                "ast": _safe_int(totals_row.get("Ast")),
                "tov": _safe_int(totals_row.get("TO")),
                "stl": _safe_int(totals_row.get("STL")),
                "blk": _safe_int(totals_row.get("BLK")),
                "pf": _safe_int(totals_row.get("PF")),
                "pts": _safe_int(totals_row.get("PTS")),
            }
            ts.update(
                four_factors.get(
                    team_id,
                    {"efg_pct": None, "tov_pct": None, "orb_pct": None, "ft_rate": None},
                )
            )
            team_stats.append(ts)
        else:
            print(f"  [WARN] no se encontro la fila de totales de equipo en {boxscore_url} "
                  f"(team_id={team_id}).")

        for _, prow in pt.iterrows():
            name = str(prow.get("Player", "")).strip()
            if not name or name.lower() == "team" or name.lower() == "nan":
                continue
            fgm, fga = _parse_made_att(prow.get("FGM-A"))
            fg3m, fg3a = _parse_made_att(prow.get("3PM-A"))
            ftm, fta = _parse_made_att(prow.get("FTM-A"))
            player_stats.append({
                "team_id": team_id,
                "player_name": name,
                "minutes": _safe_minutes(prow.get("Min")),
                "fg2_made": (fgm - fg3m) if fgm is not None and fg3m is not None else None,
                "fg2_att": (fga - fg3a) if fga is not None and fg3a is not None else None,
                "fg3_made": fg3m,
                "fg3_att": fg3a,
                "ft_made": ftm,
                "ft_att": fta,
                "pts": _safe_int(prow.get("PTS")),
                "reb": _safe_int(prow.get("Reb")),
                "ast": _safe_int(prow.get("Ast")),
                "stl": _safe_int(prow.get("STL")),
                "blk": _safe_int(prow.get("BLK")),
                "tov": _safe_int(prow.get("TO")),
                "pf": _safe_int(prow.get("PF")),
                "valuation": _safe_int(prow.get("FIC")),
            })

    return {
        "home_score": home_score,
        "away_score": away_score,
        "team_stats": team_stats,
        "player_stats": player_stats,
    }


def _safe_int(val):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _safe_float(val):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
            return None
        return float(str(val).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def _safe_minutes(val):
    """'31:18' -> 31.3 (minutos decimales, mismo formato que ya usaba el resto del pipeline)."""
    s = str(val).strip()
    m = re.match(r"(\d+):(\d+)", s)
    if not m:
        return _safe_float(s)
    mins, secs = int(m.group(1)), int(m.group(2))
    return round(mins + secs / 60, 1)


if __name__ == "__main__":
    import sys
    season = sys.argv[1] if len(sys.argv) > 1 else "2026-2027"
    result = get_season_games(season)
    print(f"{len(result)} partidos encontrados para {season}.")
    for g in result[:10]:
        print(g)
