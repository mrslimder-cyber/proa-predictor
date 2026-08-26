"""
Genera, para cada partido ya finalizado, las claves estadísticas de por qué
ganó un equipo y un resumen en texto.

Por qué no usamos un LLM para "decidir" las claves:
La parte que importa (qué estadísticas explican la victoria) la calculamos
con datos duros: comparamos las team_game_stats de ambos equipos en ESE
partido y ponderamos cada diferencia por la importancia de features que el
propio clasificador (models/train_model.py) aprendió al entrenar con todo
el histórico (models/artifacts/feature_importance_<version>.csv). Así las
claves no son un texto inventado, están ancladas al mismo modelo que genera
las predicciones. Solo la REDACCIÓN final es una plantilla de texto fija
(no generativa), así que el resultado es 100% determinista y auditable.

Uso:
    python -m models.game_insights
"""
import json

import joblib
import pandas as pd

from config import MODELS_DIR, MODEL_VERSION
from db.database import get_session
from db.models import Game, TeamGameStats, Team, GameInsight

# stat interna -> (etiqueta visible, prefijo de feature en feature_importance
# que mejor la representa, si "más alto es mejor" para ganar)
STAT_DEFS = {
    "pts":     ("Puntos anotados", None, True),
    "efg_pct": ("Efectividad de tiro (eFG%)", "efg_for", True),
    "tov":     ("Pérdidas cometidas", "tov_pct", False),
    "orb_pct": ("Rebote ofensivo %", "orb_pct", True),
    "ft_rate": ("Ratio de tiros libres", "ft_rate", True),
    "ast":     ("Asistencias", None, True),
    "reb":     ("Rebotes totales", None, True),
    "stl":     ("Robos de balón", None, True),
    "blk":     ("Tapones", None, True),
}

# peso mínimo para stats que no tienen una feature de importancia asociada
# directamente (pts, ast, reb, stl, blk no entran así en el dataset de
# entrenamiento, que usa medias móviles en su lugar); evita que desaparezcan
# del todo del ranking de claves.
_FALLBACK_WEIGHT = 0.01


def _load_feature_weights() -> dict:
    """
    Suma la importancia de home_<stat>_rN + away_<stat>_rN para cada stat
    base, así sabemos cuánto "pesa" cada una según lo que aprendió el
    modelo, independientemente de la ventana temporal (r3/r5/r10) o de si
    es home o away.
    """
    path = MODELS_DIR / f"feature_importance_{MODEL_VERSION}.csv"
    if not path.exists():
        return {}
    imp = pd.read_csv(path, index_col=0).squeeze("columns")
    weights: dict[str, float] = {}
    for key in imp.index:
        for prefix in ("home_", "away_"):
            if key.startswith(prefix):
                base = key[len(prefix):]
                weights[base] = weights.get(base, 0.0) + float(imp[key])
    return weights


def _weight_for(stat_key: str, weights: dict) -> float:
    _, importance_prefix, _ = STAT_DEFS[stat_key]
    if importance_prefix is None or not weights:
        return _FALLBACK_WEIGHT
    matches = [v for k, v in weights.items() if k.startswith(importance_prefix)]
    return max(matches) if matches else _FALLBACK_WEIGHT


def build_key_factors(home_stats: dict, away_stats: dict, weights: dict) -> list[dict]:
    """
    Devuelve la lista de factores (uno por stat disponible), ordenada de
    más a menos relevante. `favors` indica a qué equipo beneficia esa
    diferencia concreta; `score` es la magnitud de la diferencia ponderada
    por la importancia del modelo (a mayor score, más "explica" el partido).
    """
    factors = []
    for stat_key, (label, _, higher_is_better) in STAT_DEFS.items():
        h, a = home_stats.get(stat_key), away_stats.get(stat_key)
        if h is None or a is None:
            continue
        raw_diff = (h - a) if higher_is_better else (a - h)
        favors = "home" if raw_diff > 0 else ("away" if raw_diff < 0 else "empate")
        weight = _weight_for(stat_key, weights)
        factors.append({
            "stat": stat_key,
            "label": label,
            "home": round(float(h), 3),
            "away": round(float(a), 3),
            "favors": favors,
            "diff": round(abs(float(raw_diff)), 3),
            "weight": round(float(weight), 5),
        })

    for f in factors:
        f["score"] = round(f["diff"] * f["weight"], 5)

    factors.sort(key=lambda f: f["score"], reverse=True)
    return factors


def build_summary(home_name: str, away_name: str, home_won: bool, factors: list[dict]) -> str:
    winner, loser = (home_name, away_name) if home_won else (away_name, home_name)
    winner_side = "home" if home_won else "away"
    loser_side = "away" if home_won else "home"

    top = [f for f in factors if f["favors"] == winner_side][:3]
    against = [f for f in factors if f["favors"] == loser_side][:1]

    if not top:
        return f"{winner} se impuso a {loser} en un partido muy igualado en las estadísticas clave."

    partes = []
    for f in top:
        val_winner = f[winner_side]
        val_loser = f[loser_side]
        partes.append(f"{f['label'].lower()} ({val_winner:.1f} vs {val_loser:.1f})")

    texto = f"{winner} ganó a {loser} apoyándose sobre todo en: " + "; ".join(partes) + "."
    if against:
        f = against[0]
        texto += f" Aun así, cedió terreno en {f['label'].lower()}."
    return texto


def generate_all(save: bool = True) -> list[dict]:
    """
    Recorre todos los partidos finalizados que todavía no tienen insight
    guardado para MODEL_VERSION, calcula sus claves y las guarda en
    game_insights. Devuelve la lista de insights generados (útil para
    testear sin depender de leer la BD después).
    """
    weights = _load_feature_weights()

    with get_session() as session:
        finished = session.query(Game).filter(Game.status == "final").all()
        existing_ids = {
            gi.game_id for gi in
            session.query(GameInsight).filter(GameInsight.model_version == MODEL_VERSION).all()
        }
        teams = {t.id: t.name for t in session.query(Team).all()}
        stats_rows = session.query(TeamGameStats).all()

    stats_by_game: dict[int, dict[int, dict]] = {}
    for s in stats_rows:
        stats_by_game.setdefault(s.game_id, {})[s.team_id] = {
            "pts": s.pts, "efg_pct": s.efg_pct, "tov": s.tov,
            "orb_pct": s.orb_pct, "ft_rate": s.ft_rate,
            "ast": s.ast, "reb": s.reb, "stl": s.stl, "blk": s.blk,
        }

    pending = [g for g in finished if g.id not in existing_ids]
    print(f"{len(pending)} partidos finalizados sin insight todavía "
          f"(de {len(finished)} finalizados en total).")

    generated = []
    with get_session() as session:
        for g in pending:
            game_stats = stats_by_game.get(g.id)
            if not game_stats or g.home_team_id not in game_stats or g.away_team_id not in game_stats:
                # boxscore incompleto (p. ej. falló el scraping de ese partido);
                # se generará en cuanto se rellene, no lo marcamos como hecho.
                continue
            if g.home_score is None or g.away_score is None:
                continue

            home_stats = game_stats[g.home_team_id]
            away_stats = game_stats[g.away_team_id]
            factors = build_key_factors(home_stats, away_stats, weights)
            home_won = g.home_score > g.away_score
            summary = build_summary(
                teams.get(g.home_team_id, "Equipo local"),
                teams.get(g.away_team_id, "Equipo visitante"),
                home_won, factors,
            )
            winner_id = g.home_team_id if home_won else g.away_team_id

            session.merge(GameInsight(
                game_id=g.id,
                model_version=MODEL_VERSION,
                winner_team_id=winner_id,
                key_factors=json.dumps(factors, ensure_ascii=False),
                summary_text=summary,
            ))
            generated.append({
                "game_id": g.id,
                "winner_team_id": winner_id,
                "key_factors": factors,
                "summary_text": summary,
            })

    if save:
        print(f"{len(generated)} insights nuevos guardados en game_insights.")
    return generated


if __name__ == "__main__":
    generate_all()
