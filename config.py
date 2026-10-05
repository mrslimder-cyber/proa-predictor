"""
Configuracion central del proyecto ProA Predictor.

Todas las rutas, URLs base y parametros ajustables viven aqui para que
no haya "magic strings" repartidos por el codigo.
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
# Por defecto SQLite local. Cuando pases a produccion, define DATABASE_URL
# en un .env, por ejemplo la connection string de Supabase/Postgres:
#   DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/proa.db")

# --- Fuente de datos: RealGM ---
# CAMBIO: antes Proballers (scraper/proballers_scraper.py, eliminado --
# empezo a devolver 403 Forbidden en todo el historico) y, para la
# temporada en curso, 2basketballbundesliga.de + un widget en vivo via
# Playwright (scraper/bundesliga_scraper.py y
# scraper/live_boxscore_scraper.py, tambien eliminados -- el widget no
# conserva boxscore una vez el partido termina). Ahora UNA sola fuente,
# RealGM, sirve igual de bien historico y temporada actual. Ver
# scraper/realgm_scraper.py para el detalle y los avisos de que verificar.
REALGM_BASE = "https://basketball.realgm.com"
REALGM_LEAGUE_ID = 94  # German Pro A
REALGM_LEAGUE_URL = f"{REALGM_BASE}/international/league/{REALGM_LEAGUE_ID}/German-Pro-A"

# RealGM quita los acentos en los slugs de equipo (Tubingen, Koeln...).
# Aqui se restauran por id de equipo (estable). Anade mas si ves nombres raros.
TEAM_NAME_OVERRIDES = {
    684: "Walter Tigers Tübingen",
    1375: "Nürnberg Falcons BC",
    1665: "Rhein Stars Köln",
    377: "Eisbären Bremerhaven",
    681: "BG Göttingen",
    1179: "WWU Baskets Münster",
}

# Cabeceras "educadas" para el scraper: identifican el bot y evitan bloqueos
# agresivos. Ajusta el user-agent si el sitio empieza a devolver 403.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://basketball.realgm.com/",
    "Upgrade-Insecure-Requests": "1",
}
REQUEST_DELAY_SECONDS = 0.7  # cortesia entre requests para no saturar el sitio
REQUEST_TIMEOUT = 20

# --- Temporadas ---
# La proxima temporada (la que "empieza manana"): todavia sin partidos
# jugados hasta que arranque de verdad. Es la que predict.py trata como
# "proximos partidos a predecir" en cuanto haya calendario publicado.
CURRENT_SEASON = "2026-2027"

# Temporadas ya completadas que usamos como base historica de entrenamiento.
# RealGM cubre esto mismo hacia atras hasta 2012-2013 si quieres ampliar
# el rango.
HISTORICAL_SEASONS = []

# Todas las temporadas que el pipeline de ingesta recorre, en orden
# cronologico (importante: el Elo y las medias moviles se acumulan en
# este orden, asi que las historicas van antes que la actual).
ALL_SEASONS = HISTORICAL_SEASONS + [CURRENT_SEASON]

# --- Parametros del sistema Elo ---
ELO_INITIAL_RATING = 1500
ELO_K_FACTOR = 20          # sensibilidad a resultados recientes
ELO_HOME_ADVANTAGE = 60    # puntos elo anadidos al equipo local
ELO_MARGIN_MULTIPLIER = True  # si True, victorias por mas puntos pesan mas

# --- Feature engineering ---
ROLLING_WINDOWS = [3, 5, 10]     # partidos hacia atras para medias moviles
MIN_GAMES_FOR_FEATURES = 3       # partidos minimos jugados antes de confiar en las medias

# Ya no se usa activamente (scraper/bridge.py.backfill_new_teams() esta
# deshabilitado hasta tener una fuente RealGM verificada para el
# calendario de temporadas pasadas de un equipo nuevo -- ver cabecera de
# ese modulo). Se deja aqui por si se retoma.
BRIDGE_GAMES_PER_TEAM = 4

# --- Modelo ---
MODEL_VERSION = "v1"
TEST_SIZE_FRACTION = 0.2   # split temporal, no aleatorio (ver train_model.py)
RANDOM_STATE = 42
