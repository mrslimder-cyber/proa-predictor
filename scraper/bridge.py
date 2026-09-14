"""
scraper/bridge.py

Partidos "puente" para equipos NUEVOS en la temporada actual de Pro A
(ascendidos desde ProB o descendidos desde la BBL), que no tienen NINGÚN
partido en nuestra base de datos todavía.

Sin esto, el pipeline necesita MIN_GAMES_FOR_FEATURES partidos de Pro A
jugados antes de poder calcular features (medias móviles, Elo con
histórico) para un equipo nuevo -- así que su primer partido real de Pro A
se queda sin predicción, aunque el equipo sí tenga forma reciente real
(solo que en otra competición).

Estrategia: para cada equipo nuevo, scrapeamos sus últimos
BRIDGE_GAMES_PER_TEAM partidos de la TEMPORADA ANTERIOR desde la ficha
propia de ESE equipo en Proballers (no desde el calendario de la liga
Pro A) -- esa ficha lista los partidos del equipo en CUALQUIER competición
en la que jugara (BBL, ProB, Champions League...). Confirmado en vivo con
el caso real de Heidelberg (id 1774), descendido de la BBL a la Pro A
2026-2027: su ficha en
https://www.proballers.com/es/baloncesto/equipo/1774/mlp-academics-heidelberg/calendario/2025
lista sus 34 partidos de "Germany - easyCredit BBL" 2025-2026.

Solo necesitamos resultado + fecha, no boxscore completo, así que esto es
mucho más ligero que el scraping normal de temporada (no se llama a
get_boxscore() aquí).

Al rival de esos partidos puente NO lo modelamos (normalmente es un
equipo que nunca jugará en Pro A): se trata como de fuerza media (Elo
inicial) solo para poder mover el rating de NUESTRO equipo con esos
resultados.

Estos partidos NO se guardan en `games`/`team_game_stats` (esas tablas
alimentan la web vía Supabase) -- viven en su propia tabla
`bridge_game_results`, de uso exclusivamente interno del pipeline de
Python. No requiere ningún cambio en supabase/schema.sql ni en el
frontend.

Uso:
    from scraper.bridge import backfill_new_teams
    backfill_new_teams()   # se llama automáticamente al final de scraper.ingest.run_all_seasons()
"""
import re

from config import BRIDGE_GAMES_PER_TEAM, CURRENT_SEASON, ELO_INITIAL_RATING
from db.database import get_session
from db.models import BridgeGameResult, Game, Team
from config import PROBALLERS_BASE
from scraper.proballers_scraper import (
    GAME_HREF_RE, _extract_date_from_href, _get,
)

_GHOST_TEAM_ID = -1  # id "fantasma" para el rival en partidos puente; nunca persiste entre llamadas


def get_team_bridge_games(team_id: int, team_slug: str, season: str, max_games: int = BRIDGE_GAMES_PER_TEAM) -> list[dict]:
    """
    Devuelve hasta `max_games` partidos (los más recientes, orden
    cronológico) que jugó `team_id` en `season`, en cualquier competición,
    leyendo la ficha propia del equipo en Proballers.

    OJO: el slug de un equipo puede NO ser el mismo entre temporadas o
    competiciones distintas (p.ej. "heidelberg" en la Pro A 2026-2027
    frente a "mlp-academics-heidelberg" en la BBL 2025-2026, mismo id de
    equipo). Asumimos que Proballers resuelve la página por id y usa el
    slug solo para SEO/estética -- así es como se comporta la mayoría de
    sitios con este patrón de URL. Si ves warnings de fallo de carga aquí,
    entra al navegador a la ficha del equipo en cuestión (busca su nombre
    en Proballers), copia el slug real de esa temporada/competición y
    ajusta esta función si hiciera falta.
    """
    start_year = season.split("-")[0]
    url = f"{PROBALLERS_BASE}/baloncesto/equipo/{team_id}/{team_slug}/calendario/{start_year}"

    try:
        soup = _get(url)
    except Exception as e:
        print(f"  [WARN] no se pudo cargar el calendario puente de {team_slug} ({url}): {e}")
        return []

    game_links = soup.find_all("a", href=GAME_HREF_RE)
    seen_ids = set()
    results = []

    for link in game_links:
        m = GAME_HREF_RE.search(link["href"])
        if not m:
            continue
        game_id, slug = int(m.group(1)), m.group(2)
        if game_id in seen_ids:
            continue
        seen_ids.add(game_id)

        game_date = _extract_date_from_href(link["href"])
        if game_date is None:
            continue

        # El slug del partido es "<home>-<away>-YYYY-MM-DD"; si empieza
        # por el slug de nuestro equipo, jugó en casa.
        is_home = slug.startswith(team_slug + "-")

        block = link.find_parent("tr")
        if block is None:
            continue
        text = block.get_text(" ", strip=True)
        # Igual que en get_season_games(): buscamos específicamente el
        # patrón "NN-NN" del marcador. En esta tabla la columna "Hora"
        # (16:30, con ":") va ANTES que "Resultado" en el texto, así que
        # no hay riesgo de confundirla con la hora; la columna "V-P"
        # (récord, tipo "9-25") va DESPUÉS del resultado, así que el
        # primer match de re.search ya es el marcador real.
        score_match = re.search(r"\b(\d{2,3})\s*[-–]\s*(\d{2,3})\b", text)
        if not score_match:
            continue  # sin marcador todavía (partido futuro) -> lo ignoramos

        home_score, away_score = int(score_match.group(1)), int(score_match.group(2))
        team_score, opp_score = (home_score, away_score) if is_home else (away_score, home_score)

        results.append({
            "game_id": game_id,
            "date": game_date,
            "is_home": is_home,
            "team_score": team_score,
            "opp_score": opp_score,
        })

    results.sort(key=lambda r: r["date"])
    return results[-max_games:]


def backfill_new_teams(season: str = CURRENT_SEASON, max_games: int = BRIDGE_GAMES_PER_TEAM):
    """
    Detecta equipos que juegan `season` (normalmente la temporada actual
    de Pro A) y no tienen NINGÚN partido en `games` de otra temporada, y
    les descarga partidos puente de la temporada anterior. Idempotente:
    si un equipo ya tiene partidos puente guardados, se salta.
    """
    with get_session() as session:
        current_team_ids = {
            tid for (tid,) in session.query(Game.home_team_id).filter(Game.season == season)
        } | {
            tid for (tid,) in session.query(Game.away_team_id).filter(Game.season == season)
        }
        teams_with_history = {
            tid for (tid,) in session.query(Game.home_team_id).filter(Game.season != season)
        } | {
            tid for (tid,) in session.query(Game.away_team_id).filter(Game.season != season)
        }
        already_bridged = {tid for (tid,) in session.query(BridgeGameResult.team_id).distinct()}

        new_team_ids = current_team_ids - teams_with_history - already_bridged
        teams_by_id = {t.id: t for t in session.query(Team).filter(Team.id.in_(new_team_ids)).all()}

    if not new_team_ids:
        print("No hay equipos nuevos sin histórico pendientes de partidos puente.")
        return

    prev_start_year = int(season.split("-")[0]) - 1
    prev_season = f"{prev_start_year}-{prev_start_year + 1}"

    print(f"{len(new_team_ids)} equipo(s) nuevo(s) en {season} sin histórico en la BD: "
          f"buscando sus últimos {max_games} partidos de {prev_season} (cualquier competición)...")

    with get_session() as session:
        for team_id in new_team_ids:
            team = teams_by_id.get(team_id)
            if team is None:
                continue
            games = get_team_bridge_games(team_id, team.slug, prev_season, max_games=max_games)
            if not games:
                print(f"  [WARN] sin partidos puente para {team.name} ({prev_season}). "
                      f"Su primer partido de Pro A seguirá sin predicción hasta acumular "
                      f"histórico real (revisa el slug si crees que sí jugó esa temporada).")
                continue
            for g in games:
                session.merge(BridgeGameResult(
                    team_id=team_id,
                    date=g["date"],
                    is_home=g["is_home"],
                    team_score=g["team_score"],
                    opp_score=g["opp_score"],
                    source_season=prev_season,
                ))
            print(f"  {team.name}: {len(games)} partidos puente guardados (de {prev_season}).")


def seed_bridge_games(team_states: dict, elo, team_state_factory):
    """
    Precalienta `team_states` (dict team_id -> TeamState) y `elo`
    (EloSystem) con los partidos puente guardados, ANTES de procesar el
    calendario real de Pro A. `team_state_factory` es la clase/función que
    crea un TeamState vacío (se recibe como parámetro para no importar
    features.feature_engineering aquí y evitar un import circular, ya que
    ese módulo es quien importa este).
    """
    with get_session() as session:
        bridge_rows = (
            session.query(BridgeGameResult)
            .order_by(BridgeGameResult.date.asc())
            .all()
        )

    for row in bridge_rows:
        state = team_states.setdefault(row.team_id, team_state_factory())

        # Rival "fantasma": rating medio, no persiste entre partidos puente
        # ni contamina el rating de ningún equipo real de Pro A.
        elo.ratings[_GHOST_TEAM_ID] = ELO_INITIAL_RATING
        if row.is_home:
            elo.update(row.team_id, _GHOST_TEAM_ID, row.team_score, row.opp_score)
        else:
            elo.update(_GHOST_TEAM_ID, row.team_id, row.opp_score, row.team_score)
        del elo.ratings[_GHOST_TEAM_ID]

        state.games_played += 1
        state.pts_for.append(row.team_score)
        state.pts_against.append(row.opp_score)
        state.margins.append(row.team_score - row.opp_score)
        state.results.append(int(row.team_score > row.opp_score))
        state.is_home_flags.append(row.is_home)
        state.last_game_date = row.date
        # Four Factors (efg/tov/orb/ft_rate) no disponibles en partidos
        # puente -- no scrapeamos boxscore aquí a propósito, para mantener
        # esto ligero. Sus medias móviles se comportarán igual que con
        # cualquier partido donde esas stats faltan (NaN).
