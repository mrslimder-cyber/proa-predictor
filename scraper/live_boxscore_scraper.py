"""
scraper/live_boxscore_scraper.py

Boxscore de un partido desde live.2basketballbundesliga.de. Esa página
es un widget JS/WebSocket -- el HTML que devuelve el servidor viene
siempre vacío ("Liveticker lädt..."), así que aquí SÍ hace falta un
navegador de verdad (Playwright) para esperar a que el JS pinte los
datos reales, en vez de requests+BeautifulSoup como en el resto del
scraper.

OJO -- sin verificar en vivo: no tuve forma de probar esto contra un
partido real ya finalizado (mi entorno no tiene salida a internet salvo
a un puñado de dominios). La estructura de columnas (2P-A-R, 3P-A-R,
FG-A-R, FT-A-R, P, As, RO-RD-RT, F, BL, ST, TO, EFF para el resumen de
equipo; Min, 2P-A-R, 3P-A-R, FT-A-R, P, AS, RB, F, BL, ST, TO, EF por
jugador) la confirmé mirando la página con el partido a 0-0, así que el
PARSEO de "12-25 48" -> (made=12, att=25) es una suposición razonable
pero no verificada con números reales. La primera vez que esto corra
contra un partido real, revisa el log (se imprime el texto crudo de cada
fila) y ajusta MADE_ATT_RE / TRIPLE_RE si el formato no encaja.

Requiere: pip install playwright && playwright install --with-deps chromium
(ver .github/workflows/pipeline.yml, ya incluye ese paso).

Uso:
    from scraper.live_boxscore_scraper import get_boxscore_live
    box = get_boxscore_live(2005820)
"""
import re
import zlib

from bs4 import BeautifulSoup

BASE_URL = "https://live.2basketballbundesliga.de/g/{game_id}?s=boxscore"

# Tiempo de espera tras cargar la página para dar tiempo a que el
# WebSocket entregue los datos. Partidos finalizados deberían cargar el
# estado final una sola vez (no siguen empujando eventos), pero por si
# acaso esperamos un poco más de lo estrictamente necesario.
LOAD_WAIT_MS = 6000

MADE_ATT_RE = re.compile(r"(\d+)\s*[-/]\s*(\d+)")
TRIPLE_RE = re.compile(r"(\d+)\s*[-/]\s*(\d+)\s*[-/]\s*(\d+)")

TEAM_STATS_HEADERS = ["2P-A-R", "3P-A-R", "FG-A-R", "FT-A-R", "P", "As", "RO-RD-RT", "F", "BL", "ST", "TO"]
PLAYER_HEADERS = ["Min", "2P-A-R", "3P-A-R", "FT-A-R", "P", "AS", "RB", "F", "BL", "ST", "TO"]


def _synthetic_player_id(team_id: int, player_name: str) -> int:
    key = f"{team_id}|{player_name.strip().lower()}"
    return 70_000_000 + (zlib.crc32(key.encode("utf-8")) % 9_000_000)


def _header_index_map(table, wanted_labels: list[str]) -> dict[str, int]:
    """Empareja cada etiqueta buscada con el índice de columna, por texto
    de cabecera (ignora saltos de línea/espacios, ej. '2P-A-R\\n2P-A R')."""
    headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
    idx = {}
    for label in wanted_labels:
        for i, h in enumerate(headers):
            if h.startswith(label):
                idx[label] = i
                break
    return idx


def _cell_text(cells, index) -> str:
    return cells[index].get_text(" ", strip=True) if index is not None and index < len(cells) else ""


def _fetch_rendered_html(game_id: int) -> str:
    from playwright.sync_api import sync_playwright  # import perezoso: no obliga a tener
    # Playwright instalado salvo cuando de verdad se usa esta fuente.

    url = BASE_URL.format(game_id=game_id)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30_000)
        page.wait_for_timeout(LOAD_WAIT_MS)
        html = page.content()
        browser.close()
        return html


def get_boxscore_live(game_id: int) -> dict:
    """
    Devuelve {"team_stats": [...], "player_stats": [...]}, con la misma
    forma de dict por fila que usa la BD (salvo team_id/is_home, que
    añade el llamador -- ver scraper/ingest.py._ingest_live_boxscore):
    la PRIMERA tabla de equipo/jugadores que aparece en la página es
    siempre el LOCAL, la segunda el VISITANTE (igual que en Proballers).
    Cada entrada de player_stats trae además "_team_index" (0 = local,
    1 = visitante) para que el llamador la traduzca a team_id real.
    """
    html = _fetch_rendered_html(game_id)
    soup = BeautifulSoup(html, "lxml")

    tables = soup.find_all("table")
    team_stats_table = None
    player_tables = []
    for t in tables:
        headers = [th.get_text(" ", strip=True) for th in t.find_all("th")]
        if not headers:
            continue
        if "Team" in headers[0] and "2P-A-R" in "".join(headers):
            team_stats_table = t
        elif "Spieler" in headers[0]:
            player_tables.append(t)

    team_stats = []
    if team_stats_table is not None:
        idx = _header_index_map(team_stats_table, TEAM_STATS_HEADERS)
        rows = team_stats_table.find_all("tr")[1:]  # salta cabecera
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            print(f"  [live-boxscore] fila equipo cruda: {[c.get_text(' ', strip=True) for c in cells]}")

            def made_att(label):
                m = MADE_ATT_RE.search(_cell_text(cells, idx.get(label)))
                return (int(m.group(1)), int(m.group(2))) if m else (None, None)

            fg2_made, fg2_att = made_att("2P-A-R")
            fg3_made, fg3_att = made_att("3P-A-R")
            ft_made, ft_att = made_att("FT-A-R")

            m_reb = TRIPLE_RE.search(_cell_text(cells, idx.get("RO-RD-RT")))
            oreb, dreb, reb = (int(m_reb.group(1)), int(m_reb.group(2)), int(m_reb.group(3))) if m_reb else (None, None, None)

            def as_int(label):
                txt = _cell_text(cells, idx.get(label))
                return int(txt) if txt.strip().lstrip("-").isdigit() else None

            team_stats.append({
                "fg2_made": fg2_made, "fg2_att": fg2_att,
                "fg3_made": fg3_made, "fg3_att": fg3_att,
                "ft_made": ft_made, "ft_att": ft_att,
                "oreb": oreb, "dreb": dreb, "reb": reb,
                "ast": as_int("As"), "tov": as_int("TO"),
                "stl": as_int("ST"), "blk": as_int("BL"), "pf": as_int("F"),
                "pts": as_int("P"),
            })

    player_stats = []
    for team_index, ptable in enumerate(player_tables[:2]):
        idx = _header_index_map(ptable, PLAYER_HEADERS)
        rows = ptable.find_all("tr")[1:]
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 5:
                continue
            name = cells[0].get_text(" ", strip=True)
            if name in ("Teamaktionen", "Gesamt", ""):
                continue
            print(f"  [live-boxscore] fila jugador cruda ({name}): "
                  f"{[c.get_text(' ', strip=True) for c in cells]}")

            def made_att(label):
                m = MADE_ATT_RE.search(_cell_text(cells, idx.get(label)))
                return (int(m.group(1)), int(m.group(2))) if m else (None, None)

            def as_int(label):
                txt = _cell_text(cells, idx.get(label))
                return int(txt) if txt.strip().lstrip("-").isdigit() else None

            fg2_made, fg2_att = made_att("2P-A-R")
            fg3_made, fg3_att = made_att("3P-A-R")
            ft_made, ft_att = made_att("FT-A-R")

            player_stats.append({
                "_team_index": team_index,  # 0 = primera tabla (local), 1 = segunda (visitante)
                "player_name": name,
                "minutes": as_int("Min"),
                "pts": as_int("P"), "reb": as_int("RB"), "ast": as_int("AS"),
                "stl": as_int("ST"), "blk": as_int("BL"), "tov": as_int("TO"),
                "pf": as_int("F"),
                "fg2_made": fg2_made, "fg2_att": fg2_att,
                "fg3_made": fg3_made, "fg3_att": fg3_att,
                "ft_made": ft_made, "ft_att": ft_att,
            })

    return {"team_stats": team_stats, "player_stats": player_stats}
