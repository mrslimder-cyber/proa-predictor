"""
Esquema de la base de datos.

Diseño pensado para que un mismo partido tenga:
- 1 fila en `games` (metadatos: fecha, equipos, resultado)
- 2 filas en `team_game_stats` (una por equipo, con sus stats de ese partido)
- N filas en `player_game_stats` (una por jugador que participó)

Esto facilita muchísimo el feature engineering porque puedes agrupar por
team_id y ordenar por fecha para sacar medias móviles, splits casa/fuera, etc.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    # OJO: id es la clave primaria por sí sola (viene de Proballers y es
    # estable para el mismo club a través de temporadas). No hay una fila
    # por (equipo, temporada) -- solo una fila por equipo, y `season` se
    # actualiza a la temporada más reciente en la que lo hemos visto.
    # Esto es necesario porque games.home_team_id/away_team_id apuntan a
    # teams.id como clave foránea simple.
    id = Column(Integer, primary_key=True)  # usamos el id de Proballers directamente
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    season = Column(String, nullable=False)  # última temporada en la que se le vio jugar


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)  # id del partido en Proballers
    season = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    matchday = Column(Integer, nullable=True)  # jornada, si se puede inferir

    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    status = Column(String, default="scheduled")  # scheduled | final

    scraped_at = Column(DateTime, default=datetime.utcnow)

    team_stats = relationship("TeamGameStats", back_populates="game", cascade="all, delete-orphan")
    player_stats = relationship("PlayerGameStats", back_populates="game", cascade="all, delete-orphan")


class TeamGameStats(Base):
    """Estadísticas de UN equipo en UN partido concreto."""
    __tablename__ = "team_game_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    is_home = Column(Boolean, nullable=False)

    # Básicas
    fg2_made = Column(Integer)
    fg2_att = Column(Integer)
    fg3_made = Column(Integer)
    fg3_att = Column(Integer)
    ft_made = Column(Integer)
    ft_att = Column(Integer)
    oreb = Column(Integer)
    dreb = Column(Integer)
    reb = Column(Integer)
    ast = Column(Integer)
    tov = Column(Integer)   # pérdidas (Bp en la web)
    stl = Column(Integer)   # robos (Br)
    blk = Column(Integer)   # tapones
    pf = Column(Integer)    # faltas
    pts = Column(Integer)

    # Four Factors (ya vienen calculados en Proballers, los guardamos tal cual)
    efg_pct = Column(Float)
    tov_pct = Column(Float)
    orb_pct = Column(Float)
    ft_rate = Column(Float)

    game = relationship("Game", back_populates="team_stats")

    __table_args__ = (UniqueConstraint("game_id", "team_id", name="uq_game_team"),)


class PlayerGameStats(Base):
    """Estadísticas de UN jugador en UN partido concreto."""
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    player_id = Column(Integer, nullable=False)  # id del jugador en Proballers
    player_name = Column(String, nullable=False)

    minutes = Column(Float)
    pts = Column(Integer)
    reb = Column(Integer)
    ast = Column(Integer)
    stl = Column(Integer)
    blk = Column(Integer)
    tov = Column(Integer)
    pf = Column(Integer)
    valuation = Column(Integer)  # "Val" - eficiencia estilo PIR/EFF

    fg2_made = Column(Integer)
    fg2_att = Column(Integer)
    fg3_made = Column(Integer)
    fg3_att = Column(Integer)
    ft_made = Column(Integer)
    ft_att = Column(Integer)

    game = relationship("Game", back_populates="player_stats")


class TeamRating(Base):
    """
    Snapshot del rating de un equipo justo ANTES de un partido dado.
    Guardamos esto en vez de recalcular Elo en caliente cada vez, para
    poder auditar cómo evolucionó el rating a lo largo de la temporada
    y para no filtrar información del futuro al modelo (data leakage).
    """
    __tablename__ = "team_ratings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)  # partido al que precede este rating
    date = Column(DateTime, nullable=False)

    elo_pre_game = Column(Float, nullable=False)

    __table_args__ = (UniqueConstraint("team_id", "game_id", name="uq_team_game_rating"),)


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    model_version = Column(String, nullable=False)

    home_win_prob = Column(Float, nullable=False)
    predicted_margin = Column(Float, nullable=True)  # diferencia de puntos estimada (local - visitante)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("game_id", "model_version", name="uq_game_model"),)


class GameInsight(Base):
    """
    "Claves del partido": para un partido ya finalizado, guarda qué
    estadísticas explican mejor la victoria (comparando ambos equipos y
    ponderando por la importancia de features que el propio clasificador
    aprendió al entrenar) y un resumen en texto listo para mostrar.

    Se genera una vez por partido y por versión de modelo (igual que
    Prediction), así que si reentrenas con una versión nueva puedes tener
    varias explicaciones (una por MODEL_VERSION) sin pisar la anterior.
    """
    __tablename__ = "game_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    model_version = Column(String, nullable=False)

    winner_team_id = Column(Integer, nullable=False)
    # JSON (string) con la lista de factores clave, ordenados por relevancia:
    # [{"stat": "efg_pct", "label": "...", "home": 0.52, "away": 0.41,
    #   "favors": "home", "diff": 0.11, "weight": 0.03, "score": 0.0036}, ...]
    key_factors = Column(String, nullable=False)
    summary_text = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("game_id", "model_version", name="uq_game_insight_model"),)
