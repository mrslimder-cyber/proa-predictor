"""
Genera predicciones para los partidos pendientes (status='scheduled'),
reutilizando toda la lógica de estado (Elo, medias móviles, etc.) de
feature_engineering.py pero parándose justo antes de cada partido futuro
en vez de solo en partidos ya jugados.

Uso:
    python -m models.predict
"""
import joblib
import numpy as np
import pandas as pd

from config import MODELS_DIR, MODEL_VERSION, MIN_GAMES_FOR_FEATURES, ROLLING_WINDOWS
from db.database import get_session
from db.models import Game, TeamGameStats, Prediction
from features.elo import EloSystem
from features.feature_engineering import TeamState, _safe_stat


def _rebuild_state_up_to_today():
    """
    Recorre TODOS los partidos finalizados (en orden) para reconstruir
    el estado (Elo + históricos) de cada equipo justo en el momento actual,
    exactamente igual que hace build_dataset() pero sin generar filas de
    entrenamiento: solo nos interesa el estado final.
    """
    with get_session() as session:
        finished = (
            session.query(Game)
            .filter(Game.status == "final")
            .order_by(Game.date.asc())
            .all()
        )
        upcoming = (
            session.query(Game)
            .filter(Game.status != "final")
            .order_by(Game.date.asc())
            .all()
        )
        stats_rows = session.query(TeamGameStats).all()

    stats_by_game = {}
    for s in stats_rows:
        stats_by_game.setdefault(s.game_id, {})[s.team_id] = {
            "efg_pct": s.efg_pct, "tov_pct": s.tov_pct,
            "orb_pct": s.orb_pct, "ft_rate": s.ft_rate,
        }

    elo = EloSystem()
    team_states: dict[int, TeamState] = {}

    for g in finished:
        home_state = team_states.setdefault(g.home_team_id, TeamState())
        away_state = team_states.setdefault(g.away_team_id, TeamState())
        elo.update(g.home_team_id, g.away_team_id, g.home_score, g.away_score)

        game_stats = stats_by_game.get(g.id, {})
        for team_id, state, pts_for, pts_against, is_home in (
            (g.home_team_id, home_state, g.home_score, g.away_score, True),
            (g.away_team_id, away_state, g.away_score, g.home_score, False),
        ):
            ts = game_stats.get(team_id, {})
            opp_ts = game_stats.get(g.away_team_id if is_home else g.home_team_id, {})
            state.games_played += 1
            state.pts_for.append(pts_for)
            state.pts_against.append(pts_against)
            state.margins.append(pts_for - pts_against)
            state.results.append(int(pts_for > pts_against))
            state.is_home_flags.append(is_home)
            state.efg_for.append(_safe_stat(ts, "efg_pct"))
            state.efg_against.append(_safe_stat(opp_ts, "efg_pct"))
            state.tov_pct_for.append(_safe_stat(ts, "tov_pct"))
            state.orb_pct_for.append(_safe_stat(ts, "orb_pct"))
            state.ft_rate_for.append(_safe_stat(ts, "ft_rate"))
            state.last_game_date = g.date

    return elo, team_states, upcoming


def _features_for_matchup(elo, team_states, home_id, away_id, game_date) -> dict:
    home_state = team_states.get(home_id, TeamState())
    away_state = team_states.get(away_id, TeamState())
    home_elo, away_elo = elo.get_rating(home_id), elo.get_rating(away_id)

    rest_home = (game_date - home_state.last_game_date).days if home_state.last_game_date else np.nan
    rest_away = (game_date - away_state.last_game_date).days if away_state.last_game_date else np.nan

    feat = {}
    for prefix, state, elo_r in (("home", home_state, home_elo), ("away", away_state, away_elo)):
        for w in ROLLING_WINDOWS:
            feat[f"{prefix}_pts_for_r{w}"] = state.rolling(state.pts_for, w)
            feat[f"{prefix}_pts_against_r{w}"] = state.rolling(state.pts_against, w)
            feat[f"{prefix}_efg_for_r{w}"] = state.rolling(state.efg_for, w)
            feat[f"{prefix}_efg_against_r{w}"] = state.rolling(state.efg_against, w)
            feat[f"{prefix}_tov_pct_r{w}"] = state.rolling(state.tov_pct_for, w)
            feat[f"{prefix}_orb_pct_r{w}"] = state.rolling(state.orb_pct_for, w)
            feat[f"{prefix}_ft_rate_r{w}"] = state.rolling(state.ft_rate_for, w)
            feat[f"{prefix}_margin_r{w}"] = state.rolling(state.margins, w)
        feat[f"{prefix}_elo"] = elo_r
        feat[f"{prefix}_win_streak"] = state.win_streak()
        feat[f"{prefix}_games_played"] = state.games_played
        feat[f"{prefix}_home_away_split"] = state.home_away_split(prefix == "home")

    feat["home_rest_days"] = rest_home
    feat["away_rest_days"] = rest_away
    feat["elo_diff"] = home_elo - away_elo
    return feat


def predict_upcoming(save_to_db: bool = True) -> pd.DataFrame:
    clf = joblib.load(MODELS_DIR / f"win_classifier_{MODEL_VERSION}.joblib")
    reg = joblib.load(MODELS_DIR / f"margin_regressor_{MODEL_VERSION}.joblib")
    feature_cols = joblib.load(MODELS_DIR / f"feature_columns_{MODEL_VERSION}.joblib")

    elo, team_states, upcoming_games = _rebuild_state_up_to_today()

    rows = []
    for g in upcoming_games:
        home_played = team_states.get(g.home_team_id, TeamState()).games_played
        away_played = team_states.get(g.away_team_id, TeamState()).games_played
        if home_played < MIN_GAMES_FOR_FEATURES or away_played < MIN_GAMES_FOR_FEATURES:
            continue  # todavía no hay histórico suficiente para este equipo

        feat = _features_for_matchup(elo, team_states, g.home_team_id, g.away_team_id, g.date)
        feat["game_id"] = g.id
        feat["home_team_id"] = g.home_team_id
        feat["away_team_id"] = g.away_team_id
        feat["date"] = g.date
        rows.append(feat)

    if not rows:
        print("No hay partidos pendientes con histórico suficiente para predecir todavía.")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    X = df[feature_cols]

    df["home_win_prob"] = clf.predict_proba(X)[:, 1]
    df["predicted_margin"] = reg.predict(X)

    if save_to_db:
        with get_session() as session:
            for _, row in df.iterrows():
                session.merge(Prediction(
                    game_id=int(row["game_id"]),
                    model_version=MODEL_VERSION,
                    home_win_prob=float(row["home_win_prob"]),
                    predicted_margin=float(row["predicted_margin"]),
                ))
        print(f"{len(df)} predicciones guardadas en la base de datos.")

    return df[["game_id", "home_team_id", "away_team_id", "date", "home_win_prob", "predicted_margin"]]


if __name__ == "__main__":
    result = predict_upcoming()
    if not result.empty:
        pd.set_option("display.width", 120)
        print(result.to_string(index=False))
