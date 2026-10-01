"""
scraper/bridge.py

Partidos "puente" para equipos NUEVOS en la temporada actual de Pro A
(ascendidos desde ProB o descendidos desde la BBL), que no tienen NINGUN
partido en nuestra base de datos todavia. Sin esto, un equipo nuevo
necesita MIN_GAMES_FOR_FEATURES partidos reales de Pro A antes de que el
pipeline pueda calcular sus features (medias moviles, Elo con historico).

CAMBIO IMPORTANTE: la implementacion anterior (get_team_bridge_games)
leia la ficha de equipo en Proballers, fuente que ahora esta bloqueada
con 403 de forma sistematica (ver scraper/realgm_scraper.py). Todavia NO
hay una forma verificada de sacar el calendario de la temporada anterior
de un equipo recien ascendido/descendido desde RealGM, porque para eso
hace falta primero saber en que liga de RealGM jugaba ese equipo la
temporada pasada (BBL = liga 15, Pro B = liga 101, ...) y resolverlo
automaticamente no esta aun implementado.

Por eso backfill_new_teams() se deja como NO-OP informativo en vez de
una integracion a medio verificar: un equipo nuevo simplemente empieza
sin historico (igual que si este modulo no existiera) y acumula Elo y
medias moviles partido a partido real, como cualquier equipo nuevo en
MIN_GAMES_FOR_FEATURES partidos.

Si quieres retomar esto: la ficha de un equipo en RealGM si lista su
historico temporada a temporada con liga y record, por ejemplo
https://basketball.realgm.com/international/league/101/German-Pro-B/team/1174/SC-Rist-Wedel
-- el primer paso seria resolver automaticamente, a partir del nombre
del equipo nuevo, en que liga+id jugo la temporada anterior, y desde ahi
leer su calendario de esa temporada/liga.

seed_bridge_games() se mantiene SIN cambios funcionales: solo LEE lo que
ya hubiera en bridge_game_results (filas guardadas antes de este
cambio, si las hay), asi que un equipo que ya tenia partidos puente
guardados los sigue aprovechando con normalidad.

Uso:
    from scraper.bridge import backfill_new_teams, seed_bridge_games
    backfill_new_teams()   # hoy: solo informa, no descarga nada
    seed_bridge_games(team_states, elo, TeamState)  # como antes
"""
from config import CURRENT_SEASON, ELO_INITIAL_RATING
from db.database import get_session
from db.models import BridgeGameResult, Game

_GHOST_TEAM_ID = -1  # id "fantasma" para el rival en partidos puente; nunca persiste entre llamadas


def backfill_new_teams(season: str = CURRENT_SEASON, max_games: int | None = None):
    """
    DESHABILITADO (ver cabecera del modulo): no descarga nada. Solo
    detecta equipos nuevos en `season` sin ningun partido en otra
    temporada y lo informa por consola, para que sepas que ese equipo
    se va a quedar sin prediccion hasta acumular historico real.
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
        new_team_ids = current_team_ids - teams_with_history

    if new_team_ids:
        print(f"  [INFO] {len(new_team_ids)} equipo(s) nuevo(s) en {season} sin historico en la BD: "
              f"partidos puente deshabilitados (ver cabecera de scraper/bridge.py). "
              f"Acumularan Elo/medias moviles partido a partido real, sin precalentar.")


def seed_bridge_games(team_states: dict, elo, team_state_factory):
    """
    Precalienta `team_states` (dict team_id -> TeamState) y `elo`
    (EloSystem) con los partidos puente YA GUARDADOS en
    bridge_game_results, si los hay. Sin cambios respecto a la version
    anterior -- `team_state_factory` se recibe como parametro para
    evitar un import circular con features.feature_engineering.
    """
    with get_session() as session:
        bridge_rows = (
            session.query(BridgeGameResult)
            .order_by(BridgeGameResult.date.asc())
            .all()
        )

    for row in bridge_rows:
        state = team_states.setdefault(row.team_id, team_state_factory())

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
