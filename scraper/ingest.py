"""
Orquesta el scraping y vuelca todo en la base de datos.

Dos fuentes distintas según la temporada:

- Temporadas HISTÓRICAS (config.HISTORICAL_SEASONS): siguen viniendo de
  Proballers (scraper/proballers_scraper.py), calendario + boxscore,
  igual que siempre.
- Temporada EN CURSO (config.CURRENT_SEASON): calendario y resultados
  vienen de https://www.2basketballbundesliga.de/spielplan/
  (scraper/bundesliga_scraper.py), porque el calendario de Proballers
  venía fallando. El boxscore de esos partidos se saca por separado con
  un navegador headless (scraper/live_boxscore_scraper.py), ya que esa
  web no lo sirve como HTML estático.

Formas de uso:

- `run(season)` ingiere UNA temporada histórica concreta desde Proballers.
- `run_current_season_from_bundesliga(season)` ingiere la temporada en
  curso desde 2basketballbundesliga.de (calendario + resultados + boxscore
  en vivo).
- `run_all_seasons()` recorre config.ALL_SEASONS en orden cronológico,
  usando la función correcta según si la temporada es histórica o la
  actual. Esto es lo que quieres correr normalmente.

Uso:
    python -m scraper.ingest                # ingiere TODO (histórico + actual)
    python -m scraper.ingest --season 2023-2024   # ingiere solo esa temporada (Proballers)
    python -m scraper.ingest --season 2026-2027   # si es CURRENT_SEASON, usa bundesliga_scraper
"""
import argparse
import re
import unicodedata
import zlib

from tqdm import tqdm

from config import CURRENT_SEASON, HISTORICAL_SEASONS, ALL_SEASONS
from db.database import get_session, init_db
from db.models import Game, Team, TeamGameStats, PlayerGameStats
from scraper.proballers_scraper import get_season_games, get_boxscore, _team_four_factors
from scraper.bundesliga_scraper import get_current_season_games
from scraper.live_boxscore_scraper import get_boxscore_live, _synthetic_player_id
from scraper.bridge import backfill_new_teams


def upsert_teams(session, games: list[dict], season: str):
    """
    Una fila por equipo (clave = id de Proballers), no una fila por
    (equipo, temporada). Si el equipo ya existe, solo refrescamos su
    nombre/season por si ha cambiado; si no, lo creamos.
    """
    existing = {t.id: t for t in session.query(Team).all()}
    seen = set()
    for g in games:
        for team_id, name in (
            (g["home_team_id"], g["home_team_name"]),
            (g["away_team_id"], g["away_team_name"]),
        ):
            if team_id in seen:
                continue
            seen.add(team_id)
            slug = name.lower().replace(" ", "-")
            if team_id in existing:
                team = existing[team_id]
                team.name = name
                team.slug = slug
                team.season = season
            else:
                team = Team(id=team_id, name=name, slug=slug, season=season)
                session.add(team)
                existing[team_id] = team


def run(season: str = CURRENT_SEASON, only_new: bool = True):
    """
    Ingesta de UNA temporada desde Proballers. Pensada para temporadas
    HISTÓRICAS (config.HISTORICAL_SEASONS) -- la temporada en curso usa
    run_current_season_from_bundesliga() en su lugar (ver cabecera del
    archivo y run_all_seasons()).
    """
    init_db()

    print(f"Descargando calendario de la temporada {season} (Proballers)...")
    games = get_season_games(season)
    print(f"  {len(games)} partidos encontrados en el calendario.")

    if not games:
        print("  Nada que ingerir todavía para esta temporada (calendario vacío).")
        return

    with get_session() as session:
        upsert_teams(session, games, season)
        session.flush()

        # OJO: antes esto comprobaba `Game.status == "final"`, es decir "¿ya tengo
        # el resultado de este partido guardado?" -- pero el resultado se guarda en
        # el paso 1 de cada ejecución, ANTES de intentar el boxscore. Si el boxscore
        # fallaba (o get_boxscore() devolvía listas vacías sin lanzar excepción, p.ej.
        # porque no encontró las tablas esperadas en el HTML), el partido ya quedaba
        # marcado "final" y las siguientes ejecuciones lo saltaban para siempre,
        # dejando team_game_stats/player_game_stats vacías indefinidamente.
        # Ahora comprobamos si REALMENTE tenemos stats guardadas de ese partido.
        existing_stats_ids = {
            row[0] for row in session.query(TeamGameStats.game_id).distinct().all()
        }

        finished_games = [g for g in games if g["status"] == "final"]
        pending_games = [g for g in games if g["status"] != "final"]

        # 1) Guardamos/actualizamos metadatos de TODOS los partidos (incluye futuros,
        #    útil para saber qué toca predecir).
        for g in games:
            existing = session.get(Game, g["game_id"])
            if existing is None:
                session.add(Game(
                    id=g["game_id"], season=season, date=g["date"],
                    home_team_id=g["home_team_id"], away_team_id=g["away_team_id"],
                    home_score=g["home_score"], away_score=g["away_score"],
                    status=g["status"],
                ))
            else:
                existing.home_score = g["home_score"]
                existing.away_score = g["away_score"]
                existing.status = g["status"]
        session.flush()

        # 2) Boxscore detallado SOLO de partidos finalizados que aún no tenemos
        #    con stats guardadas (evita re-descargar toda la temporada cada vez).
        to_scrape = [
            g for g in finished_games
            if not only_new or g["game_id"] not in existing_stats_ids
        ]
        print(f"  {len(to_scrape)} boxscores nuevos por descargar (de {len(finished_games)} finalizados).")

        for g in tqdm(to_scrape, desc=f"Boxscores {season}"):
            try:
                box = get_boxscore(g["boxscore_url"])
            except Exception as e:
                print(f"  [WARN] fallo en boxscore de partido {g['game_id']}: {e}")
                continue

            if not box["team_stats"]:
                # get_boxscore() no lanzó excepción pero tampoco encontró las tablas
                # esperadas -> probable cambio de HTML en Proballers. Lo avisamos en
                # vez de dejarlo pasar en silencio (que es justo lo que causó el bug
                # original: partidos "procesados" sin ninguna fila guardada).
                print(f"  [WARN] boxscore de partido {g['game_id']} sin datos de equipo "
                      f"(¿cambió el HTML? revisa {g['boxscore_url']})")
                continue

            for ts in box["team_stats"]:
                session.merge(TeamGameStats(game_id=g["game_id"], **ts))

            for ps in box["player_stats"]:
                if ps.get("player_id") is None:
                    continue  # sin id no podemos deduplicar de forma fiable
                session.add(PlayerGameStats(game_id=g["game_id"], **ps))

        print(f"  {len(pending_games)} partidos aún por jugarse (quedan en estado 'scheduled').")

    print(f"Ingesta de {season} completada.")


# ---------------------------------------------------------------------------
# Temporada en curso: 2basketballbundesliga.de en vez de Proballers
# ---------------------------------------------------------------------------

def _normalize_team_name(name: str) -> str:
    """Normaliza un nombre de equipo para comparar entre fuentes distintas
    (Proballers vs 2basketballbundesliga.de pueden variar en tildes,
    mayúsculas o espacios)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name.lower())


def _resolve_team_ids_by_name(session, names: set[str]) -> dict[str, int]:
    """
    Empareja nombres de equipo (tal y como los da bundesliga_scraper) con
    los ids YA existentes en la tabla `teams` (típicamente asignados por
    Proballers en temporadas anteriores), para no perder continuidad de
    Elo/medias móviles/logos. Si un nombre no casa con ningún equipo
    existente (equipo recién ascendido, primera vez que se ve), se le
    asigna un id nuevo y estable derivado del propio nombre.
    """
    existing_by_norm = {_normalize_team_name(t.name): t.id for t in session.query(Team).all()}
    resolved = {}
    for name in names:
        norm = _normalize_team_name(name)
        if norm in existing_by_norm:
            resolved[name] = existing_by_norm[norm]
        else:
            new_id = 60_000_000 + (zlib.crc32(norm.encode("utf-8")) % 9_000_000)
            resolved[name] = new_id
            print(f"  [INFO] equipo nuevo (sin id previo en la BD): '{name}' -> id {new_id}")
    return resolved


def _ingest_live_boxscore(session, game_id: int, home_team_id: int, away_team_id: int):
    """Descarga (con navegador headless) y guarda el boxscore de UN
    partido de la temporada en curso. Nunca lanza excepción hacia
    arriba: si algo falla, lo avisa y sigue con el resto del pipeline."""
    try:
        box = get_boxscore_live(game_id)
    except Exception as e:
        print(f"  [WARN] no se pudo cargar el boxscore en vivo del partido {game_id}: {e}")
        return

    if len(box["team_stats"]) != 2:
        print(f"  [WARN] boxscore en vivo del partido {game_id} sin datos de equipo "
              f"(¿el partido no ha cargado todavía, o cambió la maquetación?).")
        return

    team_order = [home_team_id, away_team_id]
    for i, team_id in enumerate(team_order):
        ts = dict(box["team_stats"][i])
        ts["team_id"] = team_id
        ts["is_home"] = (i == 0)
        opp = box["team_stats"][1 - i]
        ts.update(_team_four_factors(ts, opp))
        session.merge(TeamGameStats(game_id=game_id, **ts))

    for ps in box["player_stats"]:
        team_id = team_order[ps.pop("_team_index")]
        ps["team_id"] = team_id
        ps["player_id"] = _synthetic_player_id(team_id, ps["player_name"])
        session.add(PlayerGameStats(game_id=game_id, **ps))


def run_current_season_from_bundesliga(season: str = CURRENT_SEASON):
    """
    Ingesta de la temporada EN CURSO desde
    https://www.2basketballbundesliga.de/spielplan/ en vez de Proballers
    (ver scraper/bundesliga_scraper.py para el porqué). Guarda calendario
    + marcador final de todos los partidos, y además descarga el
    boxscore detallado de los partidos finalizados con un navegador
    headless (scraper/live_boxscore_scraper.py), ya que esta web no lo
    sirve como HTML estático.
    """
    init_db()

    print(f"Descargando calendario de {season} desde 2basketballbundesliga.de...")
    games = get_current_season_games(season)
    print(f"  {len(games)} partidos encontrados en el calendario.")
    if not games:
        print("  Nada que ingerir todavía para esta temporada (calendario vacío).")
        return

    team_names = {g["home_team_name"] for g in games} | {g["away_team_name"] for g in games}

    with get_session() as session:
        team_ids = _resolve_team_ids_by_name(session, team_names)

        existing_teams = {t.id: t for t in session.query(Team).all()}
        for name in team_names:
            tid = team_ids[name]
            if tid in existing_teams:
                existing_teams[tid].name = name
                existing_teams[tid].season = season
            else:
                slug = name.lower().replace(" ", "-")
                session.add(Team(id=tid, name=name, slug=slug, season=season))
                existing_teams[tid] = None  # evita crearlo dos veces si se repite

        finished, pending = 0, 0
        for g in games:
            home_id = team_ids[g["home_team_name"]]
            away_id = team_ids[g["away_team_name"]]
            existing = session.get(Game, g["game_id"])
            if existing is None:
                session.add(Game(
                    id=g["game_id"], season=season, date=g["date"], matchday=g["matchday"],
                    home_team_id=home_id, away_team_id=away_id,
                    home_score=g["home_score"], away_score=g["away_score"],
                    status=g["status"],
                ))
            else:
                existing.matchday = g["matchday"]
                existing.home_score = g["home_score"]
                existing.away_score = g["away_score"]
                existing.status = g["status"]
            if g["status"] == "final":
                finished += 1
            else:
                pending += 1
        session.flush()

        print(f"  {finished} partidos finalizados, {pending} pendientes guardados.")

        existing_stats_ids = {row[0] for row in session.query(TeamGameStats.game_id).distinct().all()}
        to_scrape = [g for g in games if g["status"] == "final" and g["game_id"] not in existing_stats_ids]
        print(f"  {len(to_scrape)} boxscores en vivo nuevos por descargar (de {finished} finalizados).")
        for g in tqdm(to_scrape, desc=f"Boxscores en vivo {season}"):
            _ingest_live_boxscore(
                session, g["game_id"],
                team_ids[g["home_team_name"]], team_ids[g["away_team_name"]],
            )

    print(f"Ingesta de {season} (2basketballbundesliga.de) completada.")


def run_all_seasons(seasons: list[str] | None = None):
    """
    Recorre todas las temporadas en orden cronológico: primero el histórico
    completo (config.HISTORICAL_SEASONS, vía Proballers), luego la
    temporada actual (config.CURRENT_SEASON, vía 2basketballbundesliga.de).
    Es idempotente -- puedes correrlo varias veces, solo descarga
    boxscores de partidos que todavía no tengan stats guardadas en
    team_game_stats (no de partidos que ya estén marcados "final": eso es
    solo el resultado, no implica que el boxscore se haya guardado con éxito).
    """
    init_db()
    seasons = seasons or ALL_SEASONS
    print(f"=== Ingesta de {len(seasons)} temporadas: {', '.join(seasons)} ===\n")
    for season in seasons:
        backfill_new_teams()
        try:
            if season == CURRENT_SEASON:
                run_current_season_from_bundesliga(season)
            else:
                run(season)
        except Exception as e:
            print(f"[WARN] Fallo ingiriendo la temporada {season}: {e}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de partidos a la BD.")
    parser.add_argument(
        "--season", default=None,
        help="Temporada concreta a ingerir (ej. 2023-2024). Si se omite, ingiere TODO el histórico + la actual.",
    )
    args = parser.parse_args()

    if args.season:
        if args.season == CURRENT_SEASON:
            run_current_season_from_bundesliga(args.season)
        else:
            run(args.season)
    else:
        run_all_seasons()
