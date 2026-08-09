"""
Sistema de rating Elo para baloncesto.

Por qué Elo y no solo el balance de victorias/derrotas:
- Pondera automáticamente la fuerza del rival: ganar a un equipo top
  suma mucho más rating que ganar a un colista (esto es tu "strength
  of victory" / SOS pedido).
- Es incremental: se actualiza partido a partido, así que refleja
  racha y forma reciente de forma natural, sin tener que definir
  a mano "últimos N partidos".
- Añadimos el margen de victoria (margin multiplier) y ventaja de
  local, dos ajustes estándar en Elo para deportes (los usan FiveThirtyEight
  para NBA/NFL, por ejemplo).

Uso típico: se recorren los partidos en orden cronológico, actualizando
un diccionario {team_id: rating} y guardando el rating PRE-partido de
cada equipo antes de aplicarle el resultado (para no filtrar información
del futuro al feature engineering).
"""
import math

from config import ELO_INITIAL_RATING, ELO_K_FACTOR, ELO_HOME_ADVANTAGE, ELO_MARGIN_MULTIPLIER


class EloSystem:
    def __init__(self, initial_rating: float = ELO_INITIAL_RATING):
        self.ratings: dict[int, float] = {}
        self.initial_rating = initial_rating

    def get_rating(self, team_id: int) -> float:
        return self.ratings.get(team_id, self.initial_rating)

    def expected_win_prob(self, home_id: int, away_id: int) -> float:
        """Probabilidad de victoria del LOCAL según el rating actual (pre-partido)."""
        home_r = self.get_rating(home_id) + ELO_HOME_ADVANTAGE
        away_r = self.get_rating(away_id)
        return 1 / (1 + 10 ** ((away_r - home_r) / 400))

    def update(self, home_id: int, away_id: int, home_score: int, away_score: int):
        """
        Actualiza los ratings tras un partido. Devuelve (home_rating_pre,
        away_rating_pre) — los ratings ANTES de aplicar este resultado,
        que es lo que hay que usar como feature para predecir ese partido.
        """
        home_pre = self.get_rating(home_id)
        away_pre = self.get_rating(away_id)

        expected_home = self.expected_win_prob(home_id, away_id)
        actual_home = 1.0 if home_score > away_score else 0.0

        k = ELO_K_FACTOR
        if ELO_MARGIN_MULTIPLIER:
            margin = abs(home_score - away_score)
            elo_diff_winner = (home_pre - away_pre) if actual_home == 1.0 else (away_pre - home_pre)
            # Fórmula de margen de victoria estilo FiveThirtyEight: partidos
            # ajustados pesan más, goleadas contra equipos ya inferiores pesan menos.
            k *= math.log(margin + 1) * (2.2 / ((elo_diff_winner * 0.001) + 2.2))

        home_new = home_pre + k * (actual_home - expected_home)
        away_new = away_pre + k * ((1 - actual_home) - (1 - expected_home))

        self.ratings[home_id] = home_new
        self.ratings[away_id] = away_new

        return home_pre, away_pre
