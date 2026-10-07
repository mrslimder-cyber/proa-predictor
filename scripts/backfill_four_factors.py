"""
Recalcula efg_pct, tov_pct, orb_pct y ft_rate en team_game_stats para
TODOS los partidos ya guardados, con las formulas de Dean Oliver
(features/formulas.py), a partir de los conteos brutos que ya hay en la
BD (no hace falta volver a scrapear nada).

Cambio respecto a la version anterior: ft_rate pasa de FTA/FGA a
FTM/FGA (definicion original de Oliver), y todo sale de un unico modulo.

Uso:
    python scripts/backfill_four_factors.py
"""
import sys
from pathlib import Path

# Este script vive en scripts/, pero db/, config.py, etc. viven en la raiz
# del proyecto (un nivel arriba).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import defaultdict

from db.database import get_session
from db.models import TeamGameStats
from features.formulas import four_factors


def run():
    with get_session() as session:
        by_game = defaultdict(list)
        for r in session.query(TeamGameStats).all():
            by_game[r.game_id].append(r)

        updated, skipped = 0, 0
        for game_id, pair in by_game.items():
            if len(pair) != 2:
                skipped += 1
                continue
            a, b = pair
            for own, opp in ((a, b), (b, a)):
                own.efg_pct, own.tov_pct, own.orb_pct, own.ft_rate = four_factors(own, opp)
                updated += 1

    print(f"{updated} filas actualizadas ({skipped} partidos con boxscore incompleto, omitidos).")


if __name__ == "__main__":
    run()
