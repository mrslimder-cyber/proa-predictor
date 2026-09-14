"""
Recalcula efg_pct, tov_pct, orb_pct y ft_rate en team_game_stats para
TODOS los partidos ya guardados, a partir de los conteos brutos que ya
tenemos en la BD (no hace falta volver a scrapear nada).

Uso:
    python scripts/backfill_four_factors.py
"""
import sys
from pathlib import Path

# Este script vive en scripts/, pero db/, config.py, etc. viven en la raíz
# del proyecto (un nivel arriba). Sin esto, Python no encuentra el paquete
# "db" al ejecutar "python scripts/backfill_four_factors.py".
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from collections import defaultdict

from db.database import get_session
from db.models import TeamGameStats


def _four_factors(own, opp):
    fgm = (own.fg2_made or 0) + (own.fg3_made or 0)
    fga = (own.fg2_att or 0) + (own.fg3_att or 0)
    fta = own.ft_att or 0
    tov = own.tov or 0
    oreb = own.oreb or 0
    opp_dreb = opp.dreb if opp and opp.dreb is not None else None

    efg_pct = (fgm + 0.5 * (own.fg3_made or 0)) / fga if fga else None
    denom_tov = fga + 0.44 * fta + tov
    tov_pct = tov / denom_tov if denom_tov else None
    orb_pct = oreb / (oreb + opp_dreb) if (opp_dreb is not None and (oreb + opp_dreb) > 0) else None
    ft_rate = fta / fga if fga else None
    return efg_pct, tov_pct, orb_pct, ft_rate


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
                own.efg_pct, own.tov_pct, own.orb_pct, own.ft_rate = _four_factors(own, opp)
                updated += 1

    print(f"{updated} filas actualizadas ({skipped} partidos con boxscore incompleto, omitidos).")


if __name__ == "__main__":
    run()