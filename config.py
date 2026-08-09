"""
Configuración central del proyecto ProA Predictor.

Todas las rutas, URLs base y parámetros ajustables viven aquí para que
no haya "magic strings" repartidos por el código.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Rutas ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models" / "artifacts"
CHARTS_DIR = BASE_DIR / "charts" / "output"

for d in (DATA_DIR, MODELS_DIR, CHARTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Base de datos ---
# Por defecto SQLite local. Cuando pases a producción, define DATABASE_URL
# en un .env, por ejemplo la connection string de Supabase/Postgres:
#   DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/proa.db")

# --- Fuente de datos (Proballers) ---
PROBALLERS_BASE = "https://www.proballers.com/es"
PROBALLERS_LEAGUE_ID = 276  # Germany - Pro A
PROBALLERS_LEAGUE_SLUG = "germany-pro-a"
PROBALLERS_LEAGUE_URL = f"{PROBALLERS_BASE}/baloncesto/liga/{PROBALLERS_LEAGUE_ID}/{PROBALLERS_LEAGUE_SLUG}"


def season_calendar_url(season: str) -> str:
    """
    URL del calendario de UNA temporada concreta (ej. "2023-2024").

    Proballers identifica temporadas en la URL por su año de inicio
    (confirmado en otras secciones del sitio, ej. .../lideres/2023 para
    la temporada 2023-2024). Asumimos que /calendario/<año-inicio> sigue
    el mismo patrón. La temporada más reciente vive en /calendario sin
    sufijo, así que la contemplamos como caso especial.

    OJO: la primera vez que corras el scraper con conexión real, comprueba
    que esta URL carga el calendario correcto de esa temporada concreta
    (y no siempre el de la más reciente). Si Proballers usa otro patrón
    (por ejemplo "2023-2024" en vez de "2023", o un query param), ajusta
    esta única función — el resto del scraper no depende de la URL exacta.
    """
    start_year = season.split("-")[0]
    return f"{PROBALLERS_LEAGUE_URL}/calendario/{start_year}"


# URL "por defecto" (temporada más reciente publicada en Proballers).
PROBALLERS_SCHEDULE_URL = f"{PROBALLERS_LEAGUE_URL}/calendario"

# Cabeceras "educadas" para el scraper: identifican el bot y evitan bloqueos
# agresivos. Ajusta el user-agent si el sitio empieza a devolver 403.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ProAPredictorBot/1.0; "
        "+https://github.com/tu-usuario/proa-predictor)"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}
REQUEST_DELAY_SECONDS = 0.7 # cortesía entre requests para no saturar el sitio
REQUEST_TIMEOUT = 20

# --- Temporadas ---
# La próxima temporada (la que "empieza mañana"): todavía sin partidos
# jugados hasta que arranque de verdad. Es la que trata predict.py como
# "próximos partidos a predecir" en cuanto Proballers publique su calendario.
CURRENT_SEASON = "2026-2027"

# Temporadas ya completadas que usamos como base histórica de entrenamiento
# mientras CURRENT_SEASON no tiene partidos jugados. Así el modelo arranca
# con datos reales de forma, Elo por equipo y tendencias, en vez de con la
# base vacía. Ajusta el rango si quieres más o menos histórico (cada
# temporada añadida son más requests al scraper, ve con calma).
HISTORICAL_SEASONS = [
    "2022-2023",
    "2023-2024",
    "2024-2025",
    "2025-2026",
]

# Todas las temporadas que el pipeline de ingesta recorre, en orden
# cronológico (importante: el Elo y las medias móviles se acumulan en
# este orden, así que las históricas van antes que la actual).
ALL_SEASONS = HISTORICAL_SEASONS + [CURRENT_SEASON]

# --- Parámetros del sistema Elo ---
ELO_INITIAL_RATING = 1500
ELO_K_FACTOR = 20          # sensibilidad a resultados recientes
ELO_HOME_ADVANTAGE = 60    # puntos elo añadidos al equipo local
ELO_MARGIN_MULTIPLIER = True  # si True, victorias por más puntos pesan más

# --- Feature engineering ---
ROLLING_WINDOWS = [3, 5, 10]     # partidos hacia atrás para medias móviles
MIN_GAMES_FOR_FEATURES = 3       # partidos mínimos jugados antes de confiar en las medias

# --- Modelo ---
MODEL_VERSION = "v1"
TEST_SIZE_FRACTION = 0.2   # split temporal, no aleatorio (ver train_model.py)
RANDOM_STATE = 42
