"""
features/formulas.py

UNICA fuente de verdad de las formulas de Dean Oliver (Basketball on
Paper) que usa el proyecto. Todo lo que calcule Four Factors o
posesiones en Python (ingest, backfill, tests) debe pasar por aqui; la
web replica exactamente las mismas formulas en proa-web/lib/stats.ts.

Convenciones
- Los porcentajes se devuelven SIEMPRE como fraccion 0-1 (0.52, no 52).
- `own` y `opp` son dicts o filas ORM de team_game_stats con, al menos:
  fg2_made, fg2_att, fg3_made, fg3_att, ft_made, ft_att, oreb, dreb, tov, pts.
- Si falta algun conteo necesario se devuelve None (nunca se inventa un 0).

Four Factors (Oliver)
  eFG%     = (FGM + 0.5*3PM) / FGA
  TOV%     = TOV / Posesiones
  ORB%     = ORB / (FGA - FGM + 0.44(FTA - FTM))
  FT rate  = FTM / FGA            <- tiros libres ANOTADOS (no intentados)

Posesiones (Oliver, formula completa)
  Poss_equipo = 0.96*(FGA + 0.44*FTA - ORB + TOV)
  Poss_partido = media de Poss_equipo de ambos equipos (misma cifra para los dos)

Ratings (por 100 posesiones)
  ORtg = 100 * PTS / Poss        DRtg = 100 * PTS_rival / Poss
"""
from typing import Optional

FOUR_FACTOR_KEYS = ("efg_pct", "tov_pct", "orb_pct", "ft_rate")


def _g(s, key):
    """Lee un campo de un dict o de una fila ORM."""
    if s is None:
        return None
    return s.get(key) if isinstance(s, dict) else getattr(s, key, None)


def _core(s):
    """(fgm, fga, fg3m, ftm, fta, oreb, dreb, tov) o None si falta algo."""
    keys = ("fg2_made", "fg2_att", "fg3_made", "fg3_att", "ft_made", "ft_att", "oreb", "dreb", "tov")
    v = {k: _g(s, k) for k in keys}
    if any(x is None for x in v.values()):
        return None
    return (
        v["fg2_made"] + v["fg3_made"], v["fg2_att"] + v["fg3_att"], v["fg3_made"],
        v["ft_made"], v["ft_att"], v["oreb"], v["dreb"], v["tov"],
    )


def four_factors(own, opp) -> tuple:
    """(efg_pct, tov_pct, orb_pct, ft_rate) de `own`; `opp` solo aporta el DRB rival."""
    c = _core(own)
    if c is None:
        return (None, None, None, None)
    fgm, fga, fg3m, ftm, fta, oreb, _dreb, tov = c

    efg = (fgm + 0.5 * fg3m) / fga if fga else None
    denom = 0.96*(fga + (0.44 * fta) + tov)
    tov_pct = tov / denom if denom else None
    ft_rate = ftm / fga if fga else None

    opp_dreb = _g(opp, "dreb")
    orb = oreb / (oreb + opp_dreb) if opp_dreb is not None and (oreb + opp_dreb) > 0 else None
    return (efg, tov_pct, orb, ft_rate)


def apply_four_factors(team_stats: list) -> None:
    """Sobrescribe efg_pct/tov_pct/orb_pct/ft_rate en una lista de dicts de
    equipo (los 2 de un partido) con las formulas de Oliver. Asi no
    dependemos de lo que publique la fuente (escala, definicion de FTR...)."""
    for i, ts in enumerate(team_stats):
        opp = team_stats[1 - i] if len(team_stats) == 2 else None
        ts.update(zip(FOUR_FACTOR_KEYS, four_factors(ts, opp)))


def _own_possessions(own, opp) -> Optional[float]:
    c, o = _core(own), _core(opp)
    if c is None or o is None:
        return None
    fgm, fga, _fg3m, _ftm, fta, oreb, _dreb, tov = c
    opp_dreb = o[6]
    orb_share = oreb / (oreb + opp_dreb) if (oreb + opp_dreb) > 0 else 0.0
    return 0.960*(fga + (0.440 * fta) - oreb + tov)


def possessions(a, b) -> Optional[float]:
    """Posesiones del partido: media de la estimacion de ambos equipos."""
    pa, pb = _own_possessions(a, b), _own_possessions(b, a)
    if pa is None or pb is None:
        return None
    return 0.5 * (pa + pb)


def ratings(own, opp) -> Optional[tuple]:
    """(ORtg, DRtg, posesiones) de `own` en ese partido."""
    poss = possessions(own, opp)
    pts, opp_pts = _g(own, "pts"), _g(opp, "pts")
    if not poss or pts is None or opp_pts is None:
        return None
    return (100 * pts / poss, 100 * opp_pts / poss, poss)
