"""
Guarda en la tabla team_ratings el Elo de cada equipo, que es lo que lee la
pagina "Ranking Elo" de la web (proa-web/app/clasificacion).

Hasta ahora NADIE escribia en team_ratings (el Elo solo se calculaba en
memoria para entrenar y para los graficos), asi que la web ensenaba siempre
el valor por defecto (1500) o datos antiguos.

Como funciona:
  - Se reproducen en orden todos los partidos finalizados con EloSystem
    (igual que build_dataset, incluidos los partidos puente si los hay).
  - Para cada partido finalizado se guarda el Elo PRE-partido de ambos equipos.
  - Para los partidos aun por jugar se guarda el Elo ACTUAL de ambos equipos.
    Asi, la fila mas reciente de cada equipo (la que usa la web) es su Elo de hoy,
    ya con el resultado de la ultima jornada aplicado.
  - Es idempotente: borra y reescribe la tabla entera en cada ejecucion.

Uso:
    python -m features.save_ratings
"""
from db.database import get_session, init_db
from db.models import Game, TeamRating
from features.elo import EloSystem
from features.feature_engineering import TeamState
from scraper.bridge import seed_bridge_games


def save_ratings() -> int:
    init_db()
    with get_session() as session:
        games = session.query(Game).order_by(Game.date.asc(), Game.id.asc()).all()

    elo = EloSystem()
    seed_bridge_games({}, elo, TeamState)

    rows = []
    for g in games:
        if g.status != "final" or g.home_score is None or g.away_score is None:
            continue
        home_pre, away_pre = elo.update(g.home_team_id, g.away_team_id, g.home_score, g.away_score)
        rows.append((g.home_team_id, g.id, g.date, home_pre))
        rows.append((g.away_team_id, g.id, g.date, away_pre))

    # Partidos pendientes: Elo actual (tras el ultimo resultado conocido)
    for g in games:
        if g.status == "final" and g.home_score is not None and g.away_score is not None:
            continue
        rows.append((g.home_team_id, g.id, g.date, elo.get_rating(g.home_team_id)))
        rows.append((g.away_team_id, g.id, g.date, elo.get_rating(g.away_team_id)))

    with get_session() as session:
        session.query(TeamRating).delete()
        session.add_all(
            TeamRating(team_id=t, game_id=gid, date=d, elo_pre_game=float(r))
            for t, gid, d, r in rows
        )

    top = sorted(elo.ratings.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print(f"{len(rows)} filas de Elo guardadas en team_ratings "
          f"({len(elo.ratings)} equipos). Top 5 ids: "
          + ", ".join(f"{t}={r:.0f}" for t, r in top))
    return len(rows)


if __name__ == "__main__":
    save_ratings()
