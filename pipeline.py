"""
Pipeline completo, pensado para ejecutarse tras cada jornada:

1. Ingesta: descarga resultados nuevos y los guarda en la BD.
2. Entrenamiento: reentrena los modelos con todo el histórico actualizado.
3. Predicción: genera predicciones para los próximos partidos pendientes.
4. Claves de partidos: genera el resumen "por qué ganó" de los partidos
   ya finalizados que todavía no lo tengan (ver models/game_insights.py).
5. Gráficos: regenera las visualizaciones de análisis.

Uso manual:
    python pipeline.py

Uso automatizado: ver scripts/run_pipeline.sh y el ejemplo de GitHub Actions
en el README.
"""
import sys
import traceback
from datetime import datetime


def run_pipeline():
    start = datetime.now()
    print(f"=== Pipeline ProA Predictor — {start.isoformat()} ===\n")

    steps = [
        ("Ingesta de datos", _step_ingest),
        ("Entrenamiento del modelo", _step_train),
        ("Predicción de próximos partidos", _step_predict),
        ("Claves de partidos jugados", _step_insights),
        ("Generación de gráficos", _step_charts),
    ]

    for name, fn in steps:
        print(f"\n--- {name} ---")
        try:
            fn()
        except Exception:
            print(f"[ERROR] Fallo en '{name}':")
            traceback.print_exc()
            # No abortamos todo el pipeline por un fallo en un paso (p.ej.
            # si el sitio fuente está caído momentáneamente); seguimos con
            # el resto usando los datos que ya había.
            continue

    print(f"\n=== Pipeline completado en {(datetime.now() - start).total_seconds():.1f}s ===")


def _step_ingest():
    from scraper.ingest import run_all_seasons
    run_all_seasons()  # histórico completo + temporada actual, en orden


def _step_train():
    from models.train_model import train
    train()


def _step_predict():
    from models.predict import predict_upcoming
    predict_upcoming()


def _step_insights():
    from models.game_insights import generate_all
    generate_all()


def _step_charts():
    from charts.visualizations import plot_elo_evolution, plot_current_standings_by_elo, plot_feature_importance
    plot_elo_evolution()
    plot_current_standings_by_elo()
    plot_feature_importance()


if __name__ == "__main__":
    run_pipeline()
    sys.exit(0)
