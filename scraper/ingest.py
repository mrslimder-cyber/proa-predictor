"""
Orquesta el scraping y vuelca todo en la base de datos.
 
Dos formas de uso:
 
- `run(season)` ingiere UNA temporada concreta.
- `run_all_seasons()` recorre config.ALL_SEASONS en orden cronológico:
  primero todo el histórico (config.HISTORICAL_SEASONS), luego la
  temporada actual (config.CURRENT_SEASON). Esto es lo que quieres correr
  la primera vez, para construir la base histórica antes de que empiece
  la liga de verdad.
 
Uso:
    python -m scraper.ingest                # ingiere TODO (histórico + actual)
    python -m scraper.ingest --season 2023-2024   # ingiere solo esa temporada
"""
import argparse
 
from tqdm import tqdm
 
from config import CURRENT_SEASON, HISTORICAL_SEASONS, ALL_SEASONS
from db.database import get_session, init_db
from db.models import Game, Team, TeamGameStats, PlayerGameStats
from scraper.proballers_scraper import get_season_games, get_boxscore
 
 
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
    init_db()
 
    print(f"Descargando calendario de la temporada {season}...")
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
 
 
def run_all_seasons(seasons: list[str] | None = None):
    """
    Recorre todas las temporadas en orden cronológico: primero el histórico
    completo (config.HISTORICAL_SEASONS), luego la temporada actual
    (config.CURRENT_SEASON). Es idempotente -- puedes correrlo varias veces,
    solo descarga boxscores de partidos que todavía no tengan stats guardadas
    en team_game_stats (no de partidos que ya estén marcados "final": eso es
    solo el resultado, no implica que el boxscore se haya guardado con éxito).
    """
    seasons = seasons or ALL_SEASONS
    print(f"=== Ingesta de {len(seasons)} temporadas: {', '.join(seasons)} ===\n")
    for season in seasons:
        try:
            run(season)
        except Exception as e:
            print(f"[WARN] Fallo ingiriendo la temporada {season}: {e}")
        print()
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de partidos de Proballers a la BD.")
    parser.add_argument(
        "--season", default=None,
        help="Temporada concreta a ingerir (ej. 2023-2024). Si se omite, ingiere TODO el histórico + la actual.",
    )
    args = parser.parse_args()
 
    if args.season:
        run(args.season)
    else:
        run_all_seasons()