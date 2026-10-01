# ProA Predictor

Motor de prediccion de partidos de la **Pro A alemana** (2a division), basado
en Machine Learning: rating Elo con ventaja de local y margen de victoria,
Four Factors de Dean Oliver, medias moviles de forma, descanso entre
partidos, splits casa/fuera, y un modelo XGBoost (clasificacion + regresion
de margen) entrenado sobre todo ello.

Fuente de datos: [RealGM - German Pro A](https://basketball.realgm.com/international/league/94/German-Pro-A).
(Antes la fuente era Proballers; se migro porque empezo a bloquear el
scraping con 403 de forma sistematica en todo el historico -- ver
`scraper/realgm_scraper.py` para el detalle.)

## Instalacion

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # opcional, solo si vas a usar Postgres/Supabase
```

No hace falta instalar ningun navegador (Playwright) -- toda la ingesta es
HTML estatico via `requests`+`BeautifulSoup`.

## Uso rapido

Correr todo el pipeline de una vez (ingesta -> entrenamiento -> prediccion -> graficos):

```bash
python pipeline.py
```

O paso a paso, util para depurar:

```bash
python -m scraper.ingest        # descarga TODO: historico + temporada actual (RealGM)
python -m models.train_model    # entrena los modelos con lo que haya en la BD
python -m models.predict        # predice los proximos partidos pendientes
python -m charts.visualizations # genera los graficos en charts/output/
```

### Bootstrap con historico (antes de que empiece la liga)

`config.HISTORICAL_SEASONS` lista las ultimas temporadas ya completadas
(2022-2023 a 2025-2026 por defecto) y `config.CURRENT_SEASON` es la
proxima ("2026-2027" ahora mismo, ajusta cuando cambie el ano). La
primera vez que corras `python -m scraper.ingest` (o `pipeline.py`), el
scraper recorre TODO ese historico en orden cronologico y lo guarda en
la BD -- asi el Elo, las medias moviles y el modelo arrancan con una base
real de forma/tendencias por equipo en vez de estar vacios.

RealGM no expone un endpoint de calendario por temporada verificado, asi
que `scraper/realgm_scraper.get_season_games()` recorre dia a dia el
rango aproximado de cada temporada (1 sep - 30 jun, para cubrir regular
season + playoffs) consultando el marcador de ese dia. Esto es mas caro
la primera vez (un request por dia de cada temporada) que una ingesta
con calendario de una sola pagina, puede tardar bien mas de media hora
para las 4-5 temporadas de golpe -- las siguientes ejecuciones son
rapidas porque solo se descargan boxscores nuevos (`only_new=True` por
defecto).

Para ingerir solo una temporada concreta (util para depurar el scraper):
```bash
python -m scraper.ingest --season 2023-2024
```

**Importante**: revisa los avisos al principio de
`scraper/realgm_scraper.py` antes de confiar en una ingesta grande por
primera vez -- el rango de fechas de temporada, el orden local/visitante
y la deteccion de la fila de totales de equipo son heuristicas
verificadas contra partidos concretos, no contra cientos de ellos.

### Equipos nuevos (ascendidos/descendidos)

`scraper/bridge.py` (partidos "puente" para precalentar Elo/medias de un
equipo sin historico en Pro A) esta deshabilitado hoy: dependia de la
ficha de equipo en Proballers, y portarlo a RealGM requiere resolver
primero en que liga jugaba ese equipo la temporada anterior. Un equipo
nuevo simplemente empieza sin prediccion hasta acumular
`MIN_GAMES_FOR_FEATURES` partidos reales -- ver cabecera de ese archivo
si quieres retomarlo.

## Estructura del proyecto

```
proa-predictor/
├── config.py                  # toda la configuracion centralizada
├── pipeline.py                 # orquestador end-to-end
├── db/
│   ├── models.py               # esquema SQLAlchemy (equipos, partidos, stats, predicciones)
│   └── database.py             # conexion (SQLite local / Postgres en produccion)
├── scraper/
│   ├── realgm_scraper.py        # descubrimiento de partidos + boxscore (RealGM)
│   ├── bridge.py                 # partidos puente para equipos nuevos (deshabilitado, ver arriba)
│   └── ingest.py                 # vuelca lo scrapeado en la BD
├── features/
│   ├── elo.py                   # sistema de rating Elo
│   └── feature_engineering.py   # construccion del dataset de entrenamiento
├── models/
│   ├── train_model.py           # entrena clasificador + regresor (XGBoost)
│   └── predict.py               # predicciones para partidos pendientes
├── charts/
│   └── visualizations.py        # graficos de analisis (Elo, importancia de features...)
└── .github/workflows/pipeline.yml  # automatizacion tras cada jornada
```

## Como se evita el data leakage

Cada feature de un partido se calcula usando **solo** informacion anterior
a ese partido (medias moviles, Elo pre-partido, dias de descanso desde el
partido anterior). El propio boxscore del partido a predecir nunca entra
en sus propias features. La validacion del modelo usa un **split
temporal** (se entrena con los primeros partidos de la temporada y se
valida con los ultimos), no aleatorio, para simular como se usara en
produccion: predecir la jornada siguiente con lo que se sabe hasta hoy.

## Automatizacion ("al acabar la jornada, actualizar")

`.github/workflows/pipeline.yml` corre `python pipeline.py`
automaticamente cada domingo y lunes por la noche (ajusta el cron a como
caigan las jornadas de la Pro A), y tambien se puede lanzar a mano desde
la pestana "Actions" de GitHub.

Si migras la base de datos a Supabase/Postgres (recomendado para cuando
conectes esto con la app en Vercel), define `DATABASE_URL` como secreto en
GitHub y todo el codigo sigue funcionando igual -- solo cambia la connection
string en `config.py`.

## Nota legal

Este scraper esta pensado para uso personal/analitico sin fines
comerciales. Si el proyecto se convierte en algo publico a gran escala,
merece la pena revisar los terminos de uso de RealGM o contactar con
ellos para acceso vía API oficial en vez de scraping.
