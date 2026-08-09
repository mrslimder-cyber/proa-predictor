"""
Feature engineering.

Construye, para cada partido (jugado o futuro), un vector de features
calculado ÚNICAMENTE con información disponible ANTES de que el partido
se juegue. Esto es crítico: si se cuela una sola estadística del propio
partido a predecir, el modelo parecerá buenísimo en validación y será
inútil en producción (data leakage clásico).

Enfoque:
1. Se reconstruye la tabla de partidos + stats de equipo desde la BD.
2. Se recorre en orden cronológico, manteniendo por equipo:
   - historial de posesiones/pts a favor/en contra (para ratings ofensivo/defensivo)
   - rating Elo (vía EloSystem)
   - racha de resultados
   - fecha del último partido (para días de descanso)
   - splits casa/fuera
3. Para cada partido, se calculan features con el estado ANTERIOR a ese
   partido y luego se actualiza el estado con el resultado.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config import ROLLING_WINDOWS, MIN_GAMES_FOR_FEATURES
from db.database import get_session
from db.models import Game, TeamGameStats
from features.elo import EloSystem


def estimate_possessions(row: dict) -> float:
    """Posesiones ≈ FGA - ORB + TOV + 0.44*FTA (fórmula estándar de Dean Oliver)."""
    fga = row["fg2_att"] + row["fg3_att"]
    return fga - row["oreb"] + row["tov"] + 0.44 * row["ft_att"]


@dataclass
class TeamState:
    """Estado acumulado de un equipo a medida que avanza la temporada."""
    games_played: int = 0
    pts_for: list = field(default_factory=list)
    pts_against: list = field(default_factory=list)
    possessions: list = field(default_factory=list)
    efg_for: list = field(default_factory=list)
    efg_against: list = field(default_factory=list)
    tov_pct_for: list = field(default_factory=list)
    orb_pct_for: list = field(default_factory=list)
    ft_rate_for: list = field(default_factory=list)
    results: list = field(default_factory=list)       # 1 = victoria, 0 = derrota
    margins: list = field(default_factory=list)        # pts_for - pts_against
    is_home_flags: list = field(default_factory=list)
    last_game_date = None

    def rolling(self, values: list, window: int):
        if len(values) == 0:
            return np.nan
        return float(np.mean(values[-window:]))

    def win_streak(self) -> int:
        """Positivo = racha de victorias, negativo = racha de derrotas."""
        if not self.results:
            return 0
        streak = 0
        last = self.results[-1]
        for r in reversed(self.results):
            if r == last:
                streak += 1
            else:
                break
        return streak if last == 1 else -streak

    def home_away_split(self, home: bool, window: int = 10):
        """Diferencial medio de puntos SOLO en partidos jugados en casa (o fuera)."""
        idxs = [i for i, h in enumerate(self.is_home_flags) if h == home]
        if not idxs:
            return np.nan
        recent = idxs[-window:]
        return float(np.mean([self.margins[i] for i in recent]))


def build_dataset() -> pd.DataFrame:
    """
    Devuelve un DataFrame con una fila por partido y columnas:
    features de ambos equipos + variable objetivo (home_win, margin),
    para partidos ya finalizados. Los partidos futuros se pueden pasar
    por la misma lógica para generar features de predicción (ver predict.py).
    """
    with get_session() as session:
        games = (
            session.query(Game)
            .order_by(Game.date.asc())
            .all()
        )
        # cargamos todas las team_game_stats de golpe indexadas por game_id
        stats_rows = session.query(TeamGameStats).all()

    stats_by_game = {}
    for s in stats_rows:
        stats_by_game.setdefault(s.game_id, {})[s.team_id] = {
            "fg2_att": s.fg2_att, "fg3_att": s.fg3_att, "oreb": s.oreb,
            "tov": s.tov, "ft_att": s.ft_att, "efg_pct": s.efg_pct,
            "tov_pct": s.tov_pct, "orb_pct": s.orb_pct, "ft_rate": s.ft_rate,
        }

    elo = EloSystem()
    team_states: dict[int, TeamState] = {}
    rows = []

    for g in games:
        if g.status != "final" or g.home_score is None:
            continue  # el dataset de entrenamiento solo usa partidos jugados

        home_state = team_states.setdefault(g.home_team_id, TeamState())
        away_state = team_states.setdefault(g.away_team_id, TeamState())

        # --- Features PRE-partido (estado acumulado hasta ANTES de este juego) ---
        home_elo_pre, away_elo_pre = elo.get_rating(g.home_team_id), elo.get_rating(g.away_team_id)

        rest_home = (g.date - home_state.last_game_date).days if home_state.last_game_date else np.nan
        rest_away = (g.date - away_state.last_game_date).days if away_state.last_game_date else np.nan

        feat = {"game_id": g.id, "date": g.date}
        for prefix, state, elo_pre in (
            ("home", home_state, home_elo_pre), ("away", away_state, away_elo_pre)
        ):
            for w in ROLLING_WINDOWS:
                feat[f"{prefix}_pts_for_r{w}"] = state.rolling(state.pts_for, w)
                feat[f"{prefix}_pts_against_r{w}"] = state.rolling(state.pts_against, w)
                feat[f"{prefix}_efg_for_r{w}"] = state.rolling(state.efg_for, w)
                feat[f"{prefix}_efg_against_r{w}"] = state.rolling(state.efg_against, w)
                feat[f"{prefix}_tov_pct_r{w}"] = state.rolling(state.tov_pct_for, w)
                feat[f"{prefix}_orb_pct_r{w}"] = state.rolling(state.orb_pct_for, w)
                feat[f"{prefix}_ft_rate_r{w}"] = state.rolling(state.ft_rate_for, w)
                feat[f"{prefix}_margin_r{w}"] = state.rolling(state.margins, w)
            feat[f"{prefix}_elo"] = elo_pre
            feat[f"{prefix}_win_streak"] = state.win_streak()
            feat[f"{prefix}_games_played"] = state.games_played
            feat[f"{prefix}_home_away_split"] = state.home_away_split(prefix == "home")

        feat["home_rest_days"] = rest_home
        feat["away_rest_days"] = rest_away
        feat["elo_diff"] = home_elo_pre - away_elo_pre  # incluye ya la fuerza relativa de calendario

        # --- Variable objetivo ---
        feat["home_win"] = int(g.home_score > g.away_score)
        feat["margin"] = g.home_score - g.away_score

        rows.append(feat)

        # --- Actualizar estado POST-partido (para el siguiente partido de cada equipo) ---
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
            state.efg_for.append(ts.get("efg_pct", np.nan))
            state.efg_against.append(opp_ts.get("efg_pct", np.nan))
            state.tov_pct_for.append(ts.get("tov_pct", np.nan))
            state.orb_pct_for.append(ts.get("orb_pct", np.nan))
            state.ft_rate_for.append(ts.get("ft_rate", np.nan))
            state.last_game_date = g.date

    df = pd.DataFrame(rows)

    # Solo nos quedamos con partidos donde ambos equipos ya tienen histórico
    # mínimo; los primeros partidos de cada equipo en la temporada tienen
    # medias móviles vacías (NaN) y meterían ruido en el entrenamiento.
    mask = (df["home_games_played"] >= MIN_GAMES_FOR_FEATURES) & \
           (df["away_games_played"] >= MIN_GAMES_FOR_FEATURES)
    return df[mask].reset_index(drop=True)


def build_features_for_upcoming(team_states_snapshot=None) -> pd.DataFrame:
    """
    Placeholder de la función que generará features para partidos AÚN NO
    jugados, reutilizando el mismo TeamState/EloSystem tras procesar toda
    la temporada disputada hasta la fecha. Se completa en predict.py,
    donde hace falta cruzar esto con el calendario de partidos pendientes.
    """
    raise NotImplementedError("Ver models/predict.py")
