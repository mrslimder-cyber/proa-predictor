"""
Orquesta el scraping y vuelca todo en la base de datos.

CAMBIO: fuente UNICA para TODAS las temporadas (historicas y la actual):
RealGM (scraper/realgm_scraper.py). Antes habia dos caminos distintos
(Proballers para historico, 2basketballbundesliga.de + Playwright para
la actual); ambos se eliminan por los motivos documentados en la
cabecera de scraper/realgm_scraper.py (403 sistematico en Proballers,
boxscore en vivo vacio en el widget de bundesliga tras acabar el
partido).

Como el id de partido y el id de equipo de RealGM son estables (no hay
que recalcular un hash ni emparejar nombres), este ingest.py es mas
simple que el anterior: ya no hace falta _resolve_team_ids_by_name() ni
el workaround de ids sinteticos por CRC32.

Uso:
    python -m scraper.ingest                      # TODO el histórico + la actual
    python -m scraper.ingest --season 2025-2026    # solo esa temporada
"""
import argparse

from tqdm import tqdm
from datetime import datetime, timedelta

from config import ALL_SEASONS
from db.database import get_session, init_db
from db.models import Game, Team, TeamGameStats, PlayerGameStats
from scraper.realgm_scraper import get_season_games, get_boxscore, _season_date_range
from scraper.bridge import backfill_new_teams


def upsert_teams(session, games: list[dict], season: str):
    """Una fila por equipo (clave = id de RealGM), no una fila por
    (equipo, temporada) -- mismo criterio que antes."""
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


LOOKAHEAD_DAYS = 30  # cuanto calendario futuro se busca en cada ejecucion


def _scan_window(season: str, full: bool):
    """
    Devuelve (start, end) del rango de dias a escanear en RealGM, o None si
    la temporada ya esta completa y no hace falta tocarla.
    """
    season_start, season_end = _season_date_range(season)
    today = datetime.now()
    end = min(season_end, today + timedelta(days=LOOKAHEAD_DAYS))

    if full:
        return season_start, end

    with get_session() as session:
        games = session.query(Game.id, Game.date, Game.status).filter(Game.season == season).all()
        with_stats = {r[0] for r in session.query(TeamGameStats.game_id).distinct().all()}

    if not games:
        return season_start, end

    # Pendiente = finalizado sin boxscore guardado, o programado y reciente/futuro.
    pending = [
        d for (gid, d, st) in games
        if (st == "final" and gid not in with_stats)
        or (st != "final" and d >= today - timedelta(days=3))
    ]
    if pending:
        return min(pending) - timedelta(days=1), end

    if season_end < today:
        return None  # temporada cerrada y completa

    return max(d for (_, d, _) in games) - timedelta(days=1), end

def run(season: str, only_new: bool = True, full: bool = False):
    init_db()

    window = _scan_window(season, full)
    if window is None:
        print(f"  Temporada {season} ya completa en la BD, se omite (usa --full para forzar).")
        return
    start, end = window
    print(f"Descargando calendario de {season} (RealGM): {start.date()} -> {end.date()}")
    games = get_season_games(season, start, end)
    print(f"  {len(games)} partidos encontrados.")
    if not games:
        print("  Nada que ingerir todavia para esta temporada.")
        return

    with get_session() as session:
        upsert_teams(session, games, season)
        session.flush()

        # 1) Metadatos de TODOS los partidos (incluye los que aun no se
        #    han jugado, para saber que toca predecir). El id de RealGM
        #    es estable entre "scheduled" y "final" -- un UPDATE normal
        #    por id, sin riesgo de duplicados.
        for g in games:
            existing = session.get(Game, g["game_id"])
            if existing is None:
                session.add(Game(
                    id=g["game_id"], season=season, date=g["date"],
                    home_team_id=g["home_team_id"], away_team_id=g["away_team_id"],
                    home_score=None, away_score=None, status=g["status"],
                ))
            else:
                existing.status = g["status"]
        session.flush()

        # 2) Boxscore (marcador + stats) solo de partidos con boxscore
        #    publicado por RealGM, y solo los que aun no tengamos
        #    guardados (igual que antes: evita re-descargar la temporada
        #    entera en cada ejecucion).
        finished = [g for g in games if g["status"] == "final" and g["boxscore_url"]]
        existing_stats_ids = {
            row[0] for row in session.query(TeamGameStats.game_id).distinct().all()
        }
        to_scrape = [g for g in finished if not only_new or g["game_id"] not in existing_stats_ids]
        pending = len(games) - len(finished)
        print(f"  {len(to_scrape)} boxscores nuevos por descargar (de {len(finished)} finalizados, "
              f"{pending} aun sin jugar o sin boxscore publicado todavia por RealGM).")

        for g in tqdm(to_scrape, desc=f"Boxscores {season}"):
            try:
                box = get_boxscore(g["boxscore_url"])
            except Exception as e:
                print(f"  [WARN] fallo en boxscore del partido {g['game_id']}: {e}")
                continue

            game_row = session.get(Game, g["game_id"])
            if box["home_score"] is not None and box["away_score"] is not None:
                game_row.home_score = box["home_score"]
                game_row.away_score = box["away_score"]

            if not box["team_stats"]:
                print(f"  [WARN] boxscore de equipo vacio para el partido {g['game_id']} "
                      f"({g['boxscore_url']}) -- se reintentara en la proxima ejecucion.")
                continue

            for ts in box["team_stats"]:
                session.merge(TeamGameStats(game_id=g["game_id"], **ts))
            for ps in box["player_stats"]:
                session.add(PlayerGameStats(game_id=g["game_id"], **ps))

    print(f"Ingesta de {season} completada.")


def run_all_seasons(seasons: list[str] | None = None, full: bool = False):
    init_db()
    seasons = seasons or ALL_SEASONS
    print(f"=== Ingesta de {len(seasons)} temporadas (RealGM): {', '.join(seasons)} ===\n")
    for n, season in enumerate(seasons, 1):
        print(f"[{n}/{len(seasons)}] Temporada {season}")
        backfill_new_teams(season)
        try:
            run(season, full=full)
        except Exception as e:
            print(f"[WARN] Fallo ingiriendo la temporada {season}: {e}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta de partidos a la BD (RealGM).")
    parser.add_argument("--season", default=None, help="Temporada concreta (ej. 2025-2026).")
    parser.add_argument("--full", action="store_true",
                        help="Reescanea toda la temporada aunque ya este completa.")
    args = parser.parse_args()

    if args.season:
        run(args.season, full=args.full)
    else:
        run_all_seasons(full=args.full)
