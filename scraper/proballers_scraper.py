"""
Scraper de Proballers para la Pro A alemana.

Estrategia:
- Usamos requests + BeautifulSoup para navegar (rápido, sin JS necesario;
  las páginas de Proballers vienen renderizadas en servidor).
- Usamos pandas.read_html() para las tablas de boxscore: es más robusto
  que escribir selectores CSS frágiles, porque pandas parsea cualquier
  <table> bien formada independientemente de las clases CSS que le pongan.
- Cada partido de Proballers tiene una URL con un id numérico estable
  (ej. /partido/836706/...). Ese id es nuestra clave primaria en `games`.

IMPORTANTE: si Proballers cambia el marcado HTML, lo que más probablemente
se rompa son las funciones que extraen IDs de equipo/jugador vía regex
sobre los href (`_extract_id_from_href`). Las tablas de estadísticas
(vía read_html) son más resistentes a cambios de diseño.

CAMBIO (corrección del bug "no se guardan estadísticas de partidos"):
Proballers dejó de incluir el marcador como texto plano en la fila de
cada partido del CALENDARIO de la liga (season_calendar_url). Antes esa
fila tenía algo como ".. 69-71 .." en su texto; ahora la celda de
"Resultado" es siempre un link ("Avance del juego" / "Ver resultado"),
tanto para partidos futuros como ya finalizados. Como get_season_games()
decidía status="final" únicamente a partir de ese "NN-NN" en el texto,
todos los partidos se quedaban marcados "scheduled" para siempre y
scraper/ingest.py nunca llegaba a pedir el boxscore -> team_game_stats
vacía. La corrección: cuando la fila no trae marcador Y la fecha del
partido ya pasó, visitamos la página de ESE partido concreto y leemos el
marcador ahí, donde Proballers lo muestra junto a la palabra "Final"
(ver _get_final_score_from_game_page).
"""
import io
import re
import time
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import (
    PROBALLERS_LEAGUE_URL,
    REQUEST_HEADERS,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT,
    CURRENT_SEASON,
    season_calendar_url,
)

TEAM_HREF_RE = re.compile(r"/equipo/(\d+)/([^/]+)/")
GAME_HREF_RE = re.compile(r"/partido(?:-preview)?/(\d+)/([^/\"]+)")

# Marcador "final" tal y como aparece en la página de UN partido concreto ya
# jugado, ej. "81 - 89 Final". Se usa como fallback cuando la fila del
# calendario ya no trae el marcador como texto (ver nota arriba).
FINAL_SCORE_RE = re.compile(r"\b(\d{2,3})\s*[-–]\s*(\d{2,3})\b\s*Final", re.IGNORECASE)

SPANISH_MONTHS = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}


def _extract_date_from_href(href: str):
    """
    El slug de cada partido termina en YYYY-MM-DD, ej.
    /partido/836409/artland-dragons-wwu-munster-2025-09-26 -> 2025-09-26.
    Es la fuente de fecha más fiable (no depende de parsear texto en
    español ni de cómo esté maquetado el bloque del partido).
    """
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})(?:$|[/?#\"])", href)
    if not m:
        return None
    year, month, day = (int(x) for x in m.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _extract_date_from_text(text: str):
    """
    Fallback si el href no trae fecha: busca patrones tipo "26 sept 2025"
    o "3 oct 2025" (formato real del calendario de Proballers en español).
    """
    m = re.search(r"\b(\d{1,2})\s+([a-zA-Zñ]+)\.?\s+(\d{4})\b", text)
    if not m:
        return None
    day, month_raw, year = m.groups()
    month_key = month_raw.lower().rstrip(".")
    month_num = SPANISH_MONTHS.get(month_key) or SPANISH_MONTHS.get(month_key[:3])
    if not month_num:
        return None
    try:
        return datetime(int(year), month_num, int(day))
    except ValueError:
        return None


def _get(url: str) -> BeautifulSoup:
    """GET con cortesía (delay) y parseo a BeautifulSoup."""
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(resp.text, "lxml")


def _extract_team_from_href(href: str):
    m = TEAM_HREF_RE.search(href)
    if not m:
        return None
    team_id, slug = m.groups()
    return int(team_id), slug


def _find_game_block(link):
    """
    Sube por los ancestros del link de un partido hasta encontrar el
    contenedor MÁS PEQUEÑO que ya incluye a los 2 equipos de ESE partido.

    Deliberadamente NO buscamos por nombre de tag (div/li/article/tr):
    Proballers renderiza el calendario como una <table>, así que cada
    partido vive en un <tr>. Buscar solo div/li/article se salta la fila
    real y sube hasta el contenedor que envuelve TODA la tabla de la
    temporada -- con lo que todos los partidos de una misma temporada
    terminan leyendo el mismo bloque de texto (y por tanto el mismo
    marcador, mal). Parar en cuanto haya exactamente 1 link de partido
    (el nuestro) y 2+ links de equipo evita ese problema sin depender de
    qué tag use Proballers en cada temporada.
    """
    node = link.parent
    while node is not None:
        team_links = node.find_all("a", href=TEAM_HREF_RE)
        game_links = node.find_all("a", href=GAME_HREF_RE)
        if len(team_links) >= 2 and len(game_links) == 1:
            return node
        node = node.parent
    return None


def _get_final_score_from_game_page(game_url: str):
    """
    Visita la página de UN partido concreto y devuelve (home_score,
    away_score) leyendo el patrón "NN-NN Final" que Proballers muestra ahí
    para partidos ya finalizados (confirmado en vivo, ej. "81 - 89 Final").

    Devuelve (None, None) si el partido todavía no se ha jugado, o si no
    se pudo encontrar el marcador (p. ej. si Proballers vuelve a cambiar
    el marcado HTML) -- en ese caso el partido se deja como "scheduled" en
    vez de romper todo el scraping.
    """
    try:
        soup = _get(game_url)
    except Exception as e:
        print(f"  [WARN] no se pudo abrir la página del partido para leer el marcador ({game_url}): {e}")
        return None, None

    text = soup.get_text(" ", strip=True)
    m = FINAL_SCORE_RE.search(text)
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def get_season_games(season: str = CURRENT_SEASON) -> list[dict]:
    """
    Recorre el calendario de la liga y devuelve una lista de dicts:
        {game_id, date, home_team_id, home_team_name, away_team_id,
         away_team_name, home_score, away_score, status, boxscore_url}

    Los partidos ya jugados traen marcador; los futuros no (status='scheduled').

    OJO: el calendario de la liga ya NO incluye el marcador como texto
    plano en la fila de cada partido (ver nota al principio del archivo).
    Cuando eso pasa y la fecha del partido ya pasó, se visita la página
    de ESE partido para leer el marcador ahí (_get_final_score_from_game_page).
    Esto añade una request extra por cada partido finalizado la primera
    vez, pero scraper/ingest.py es idempotente (only_new=True), así que
    en ejecuciones futuras solo se paga por partidos nuevos.
    """
    soup = _get(season_calendar_url(season))
    games = []

    # Cada partido en el calendario es un bloque con dos links a /equipo/
    # y un link a /partido/<id>/... que sirve tanto de resultado como de
    # enlace al boxscore. Buscamos todos los anchors a /partido/ y de ahí
    # reconstruimos el contexto (equipos, marcador) mirando el bloque padre.
    game_links = soup.find_all("a", href=GAME_HREF_RE)

    seen_game_ids = set()
    fallback_used = 0
    for link in game_links:
        m = GAME_HREF_RE.search(link["href"])
        if not m:
            continue
        game_id = int(m.group(1))
        if game_id in seen_game_ids:
            continue
        seen_game_ids.add(game_id)

        # Subimos al contenedor MÍNIMO de este partido (ver _find_game_block).
        block = _find_game_block(link)
        if block is None:
            continue

        team_links = block.find_all("a", href=TEAM_HREF_RE)
        if len(team_links) < 2:
            continue

        home = _extract_team_from_href(team_links[0]["href"])
        away = _extract_team_from_href(team_links[1]["href"])
        if not home or not away:
            continue

        # Marcador: buscamos específicamente el patrón "NN-NN" (con guion,
        # sin dos puntos) para no confundirlo con la hora del partido tipo
        # "20:00", que también tiene 2 números de 2 dígitos pegados.
        # Desde que Proballers cambió el calendario, esto solo encuentra
        # algo para partidos donde el marcador SÍ sigue viniendo inline
        # (ver fallback más abajo para cuando no es así).
        score_match = re.search(r"\b(\d{2,3})\s*[-–]\s*(\d{2,3})\b", block.get_text(" ", strip=True))
        home_score = int(score_match.group(1)) if score_match else None
        away_score = int(score_match.group(2)) if score_match else None

        # Fecha: primero intentamos sacarla del propio slug del partido
        # (más fiable), y si no, la buscamos en el texto del bloque.
        game_date = _extract_date_from_href(link["href"]) or _extract_date_from_text(
            block.get_text(" ", strip=True)
        )
        if game_date is None:
            # Sin fecha no podemos ordenar cronológicamente este partido
            # (crítico para Elo/features), así que lo saltamos y lo avisamos
            # en vez de guardar una fila con date=NULL que rompe la BD.
            print(f"  [WARN] no se pudo extraer fecha del partido {game_id}, se omite.")
            continue

        boxscore_url = f"https://www.proballers.com{link['href']}" if link["href"].startswith("/") else link["href"]

        # NUEVO: fallback cuando el calendario no trae marcador inline.
        # Solo lo intentamos para partidos cuya fecha YA PASÓ -- para
        # partidos futuros, la ausencia de marcador es simplemente correcta
        # y no hace falta gastar una request extra comprobándolo.
        if home_score is None and game_date < datetime.now():
            home_score, away_score = _get_final_score_from_game_page(boxscore_url)
            if home_score is not None:
                fallback_used += 1

        games.append({
            "game_id": game_id,
            "date": game_date,
            "home_team_id": home[0],
            "home_team_name": home[1],
            "away_team_id": away[0],
            "away_team_name": away[1],
            "home_score": home_score,
            "away_score": away_score,
            "status": "final" if home_score is not None else "scheduled",
            "boxscore_url": boxscore_url,
        })

    if fallback_used:
        print(f"  {fallback_used} marcador(es) recuperado(s) visitando la página del partido "
              f"(el calendario ya no los trae como texto plano).")

    return games


def get_boxscore(game_url: str) -> dict:
    """
    Descarga y parsea el boxscore completo de un partido:
    stats de equipo (con Four Factors) y stats por jugador de ambos equipos.

    Devuelve:
        {
          "team_stats": [ {team_id, is_home, pts, reb, ast, ..., efg_pct, tov_pct, orb_pct, ft_rate}, ... ],
          "player_stats": [ {player_id, player_name, team_id, pts, reb, ast, min, ...}, ... ],
        }
    """
    soup = _get(game_url)
    # OJO: pd.read_html() con un string literal (en vez de una URL/ruta/buffer)
    # comprueba antes internamente si ese string podría ser una ruta de archivo
    # (os.path.exists(...)). En Windows, con un string tan largo como un HTML
    # completo, esa comprobación no devuelve False limpiamente: lanza un OSError
    # real ("[Errno 2] No such file or directory: <!DOCTYPE html>...") que
    # pandas no atrapa. Envolviendo el string en io.StringIO evitamos que pandas
    # intente tratarlo como ruta de archivo en absoluto.
    tables = pd.read_html(io.StringIO(str(soup)))  # todas las tablas <table> de la página

    # La tabla "Estadísticas de los equipos" es la que tiene 2 filas (una por equipo)
    # y columnas tipo 2M, 2A, 3M, 3A, FGM... La identificamos por sus columnas.
    team_stats_table = None
    player_tables = []

    for t in tables:
        cols = [str(c).strip() for c in t.columns]
        if {"2M", "2A", "Pts", "Reb", "Ast"}.issubset(set(cols)) and len(t) == 2:
            team_stats_table = t
        elif {"Pts", "Reb", "Ast", "Min"}.issubset(set(cols)):
            player_tables.append(t)

    # IDs y nombres de equipo, en orden de aparición (local primero)
    team_links = soup.find_all("a", href=TEAM_HREF_RE)
    team_order = []
    for link in team_links:
        info = _extract_team_from_href(link["href"])
        if info and info not in team_order:
            team_order.append(info)
    team_order = team_order[:2]  # local, visitante

    team_stats = []
    if team_stats_table is not None:
        for i, (team_id, _slug) in enumerate(team_order):
            row = team_stats_table.iloc[i]
            team_stats.append({
                "team_id": team_id,
                "is_home": (i == 0),
                "fg2_made": int(row.get("2M", 0)),
                "fg2_att": int(row.get("2A", 0)),
                "fg3_made": int(row.get("3M", 0)),
                "fg3_att": int(row.get("3A", 0)),
                "ft_made": int(row.get("1M", 0)),
                "ft_att": int(row.get("1A", 0)),
                "oreb": int(row.get("Ro", 0)),
                "dreb": int(row.get("Rd", 0)),
                "reb": int(row.get("Reb", 0)),
                "ast": int(row.get("Ast", 0)),
                "tov": int(row.get("Bp", 0)),
                "stl": int(row.get("Br", 0)),
                "blk": int(row.get("Tap", 0)),
                "pf": int(row.get("Fa", 0)),
                "pts": int(row.get("Pts", 0)),
            })

    # Four Factors calculados por nosotros con los conteos de ambos equipos
    # (ver _team_four_factors), no con la tabla "Four Factors" de Proballers.
    if len(team_stats) == 2:
        for i, own in enumerate(team_stats):
            opp = team_stats[1 - i]
            own.update(_team_four_factors(own, opp))

    if team_stats_table is None:
        # NUEVO: si esto se ve con frecuencia tras el cambio de calendario,
        # es señal de que Proballers también cambió la maquetación de la
        # PÁGINA del partido (no solo el calendario), y habría que revisar
        # aquí qué nombres de columna usa ahora la tabla de equipos.
        print(f"  [WARN] no se encontró la tabla de estadísticas de equipo en {game_url} "
              f"(¿cambió también el HTML de la página del partido?).")

    # Stats por jugador: cada tabla de jugadores va precedida por el nombre
    # del equipo; asumimos que aparecen en el mismo orden que team_order
    # (local primero, visitante después), que es como Proballers las pinta.
    player_stats = []
    for i, player_table in enumerate(player_tables[:2]):
        team_id = team_order[i][0] if i < len(team_order) else None
        # La última fila de cada tabla es el TOTAL del equipo -> la excluimos
        rows = player_table.iloc[:-1] if len(player_table) > 1 else player_table
        for _, prow in rows.iterrows():
            player_stats.append({
                "team_id": team_id,
                "player_name": str(prow.get("Jugador", "")).strip(),
                "minutes": _safe_float(prow.get("Min")),
                "pts": _safe_int(prow.get("Pts")),
                "reb": _safe_int(prow.get("Reb")),
                "ast": _safe_int(prow.get("Ast")),
                "stl": _safe_int(prow.get("Br")),
                "blk": _safe_int(prow.get("Tap")),
                "tov": _safe_int(prow.get("Bp")),
                "pf": _safe_int(prow.get("Fa")),
                "valuation": _safe_int(prow.get("Val")),
            })

    # player_id real: lo sacamos aparte de los <a href="/jugador/ID/slug">
    # y lo casamos por nombre (más robusto que intentar alinear filas de pandas con links del DOM)
    player_id_map = {}
    for a in soup.find_all("a", href=re.compile(r"/jugador/(\d+)/")):
        pid = int(re.search(r"/jugador/(\d+)/", a["href"]).group(1))
        name = a.get_text(strip=True)
        if name:
            player_id_map[name] = pid

    for p in player_stats:
        p["player_id"] = player_id_map.get(p["player_name"])

    return {"team_stats": team_stats, "player_stats": player_stats}


def _pct_to_float(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return float(str(val).replace("%", "").strip()) / 100

def _team_four_factors(own: dict, opp: dict) -> dict:
    """
    Four Factors de Dean Oliver, calculados a partir de los conteos brutos
    del boxscore (tabla "Estadísticas de los equipos", fiable) en vez de la
    tabla "Four Factors" que publica Proballers en la página del partido:
    hemos comprobado que esa tabla llega incompleta con frecuencia (2 de
    los 4 factores para un equipo, los otros 2 para el rival), así que ya
    no la usamos como fuente.
    """
    required_own = ("fg2_made", "fg3_made", "fg2_att", "fg3_att", "ft_att", "tov", "oreb")
    if any(own.get(k) is None for k in required_own) or opp.get("dreb") is None:
        return {"efg_pct": None, "tov_pct": None, "orb_pct": None, "ft_rate": None}

    fgm = own["fg2_made"] + own["fg3_made"]
    fga = own["fg2_att"] + own["fg3_att"]
    efg_pct = (fgm + 0.5 * own["fg3_made"]) / fga if fga else None
    denom_tov = fga + 0.44 * own["ft_att"] + own["tov"]
    tov_pct = own["tov"] / denom_tov if denom_tov else None
    orb_pct = own["oreb"] / (own["oreb"] + opp["dreb"]) if (own["oreb"] + opp["dreb"]) else None
    ft_rate = own["ft_att"] / fga if fga else None
    return {"efg_pct": efg_pct, "tov_pct": tov_pct, "orb_pct": orb_pct, "ft_rate": ft_rate}

def _safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
