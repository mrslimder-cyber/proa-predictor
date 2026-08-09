"""
Gráficos de análisis exploratorio (para investigar patrones tú y tu hermano),
separados de los gráficos que verá el usuario final en la futura app Vercel
(esos se harán con Recharts/Plotly.js en el frontend, no aquí).

Uso:
    python -m charts.visualizations
"""
import joblib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config import CHARTS_DIR, MODELS_DIR, MODEL_VERSION
from db.database import get_session
from db.models import Game, Team
from features.elo import EloSystem

sns.set_theme(style="whitegrid")


def plot_elo_evolution():
    """Evolución del rating Elo de cada equipo a lo largo de la temporada."""
    with get_session() as session:
        games = session.query(Game).filter(Game.status == "final").order_by(Game.date.asc()).all()
        teams = {t.id: t.name for t in session.query(Team).all()}

    elo = EloSystem()
    history = []
    for g in games:
        home_pre, away_pre = elo.update(g.home_team_id, g.away_team_id, g.home_score, g.away_score)
        history.append({"date": g.date, "team_id": g.home_team_id, "elo": elo.get_rating(g.home_team_id)})
        history.append({"date": g.date, "team_id": g.away_team_id, "elo": elo.get_rating(g.away_team_id)})

    if not history:
        print("Sin partidos finalizados todavía; no se puede graficar Elo.")
        return

    df = pd.DataFrame(history)
    df["team_name"] = df["team_id"].map(teams)

    plt.figure(figsize=(12, 7))
    for team_id, group in df.groupby("team_id"):
        plt.plot(group["date"], group["elo"], marker="o", markersize=3, label=teams.get(team_id, team_id))

    plt.title("Evolución del rating Elo — Pro A 2025-2026")
    plt.xlabel("Fecha")
    plt.ylabel("Elo rating")
    plt.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    plt.tight_layout()
    out = CHARTS_DIR / "elo_evolution.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"Guardado: {out}")


def plot_feature_importance():
    path = MODELS_DIR / f"feature_importance_{MODEL_VERSION}.csv"
    if not path.exists():
        print("No hay feature_importance guardado todavía; entrena el modelo primero.")
        return

    imp = pd.read_csv(path, index_col=0).squeeze("columns").sort_values(ascending=True).tail(20)

    plt.figure(figsize=(9, 8))
    imp.plot(kind="barh", color="#1f6feb")
    plt.title("Importancia de features — clasificador de victoria")
    plt.xlabel("Importancia (XGBoost)")
    plt.tight_layout()
    out = CHARTS_DIR / "feature_importance.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"Guardado: {out}")


def plot_current_standings_by_elo():
    """Ranking actual por Elo (más informativo que la clasificación oficial
    cuando los equipos no han jugado el mismo número de partidos)."""
    with get_session() as session:
        games = session.query(Game).filter(Game.status == "final").order_by(Game.date.asc()).all()
        teams = {t.id: t.name for t in session.query(Team).all()}

    elo = EloSystem()
    for g in games:
        elo.update(g.home_team_id, g.away_team_id, g.home_score, g.away_score)

    if not elo.ratings:
        print("Sin partidos finalizados todavía.")
        return

    ranking = pd.Series(elo.ratings).sort_values(ascending=False)
    ranking.index = ranking.index.map(lambda tid: teams.get(tid, tid))

    plt.figure(figsize=(9, 8))
    ranking.plot(kind="barh", color="#e3572a")
    plt.gca().invert_yaxis()
    plt.title("Ranking actual por Elo — Pro A")
    plt.xlabel("Elo rating")
    plt.tight_layout()
    out = CHARTS_DIR / "elo_ranking.png"
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"Guardado: {out}")


if __name__ == "__main__":
    plot_elo_evolution()
    plot_current_standings_by_elo()
    plot_feature_importance()
