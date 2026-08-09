# ProA Predictor

Motor de predicción de partidos de la **Pro A alemana** (2ª división), basado
en Machine Learning: rating Elo con ventaja de local y margen de victoria,
Four Factors de Dean Oliver, medias móviles de forma, descanso entre
partidos, splits casa/fuera, y un modelo XGBoost (clasificación + regresión
de margen) entrenado sobre todo ello.

Fuente de datos: [Proballers - Germany Pro A](https://www.proballers.com/es/baloncesto/liga/276/germany-pro-a).

## Instalación

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # opcional, solo si vas a usar Postgres/Supabase
```

## Uso rápido

Correr todo el pipeline de una vez (ingesta → entrenamiento → predicción → gráficos):

```bash
python pipeline.py
```

O paso a paso, útil para depurar:

```bash
python -m scraper.ingest        # descarga TODO: histórico + temporada actual
python -m models.train_model    # entrena los modelos con lo que haya en la BD
python -m models.predict        # predice los próximos partidos pendientes
python -m charts.visualizations # genera los gráficos en charts/output/
```

### Bootstrap con histórico (antes de que empiece la liga)

`config.HISTORICAL_SEASONS` lista las últimas temporadas ya completadas
(2018-2019 a 2025-2026 por defecto) y `config.CURRENT_SEASON` es la
próxima ("2026-2027" ahora mismo, ajusta cuando cambie el año). La
primera vez que corras `python -m scraper.ingest` (o `pipeline.py`), el
scraper recorre TODO ese histórico en orden cronológico y lo guarda en
la BD — así el Elo, las medias móviles y el modelo arrancan con una base
real de forma/tendencias por equipo en vez de estar vacíos, cubriendo el
hueco hasta que la 2026-2027 tenga sus primeros partidos jugados.

Esto tardará bastante la primera vez (son ~8 temporadas × ~30 partidos ×
un boxscore por partido, con pausa de cortesía entre requests — puede
ser media hora o más). Las siguientes ejecuciones son rápidas: cada
temporada solo descarga los boxscores que todavía no tenía
(`only_new=True` por defecto), así que re-correr el pipeline cada
jornada es barato.

Para ingerir solo una temporada concreta (útil para depurar el scraper):
```bash
python -m scraper.ingest --season 2023-2024
```

**Importante**: no he podido verificar en vivo el patrón exacto de URL
que usa Proballers para el calendario de temporadas pasadas (solo pude
confirmarlo indirectamente para otras secciones del sitio). La primera
vez que corras esto, revisa `config.season_calendar_url()` — si
`get_season_games()` devuelve 0 partidos para una temporada que sabes
que sí tuvo liga, seguramente haya que ajustar esa función al patrón
real que veas en la barra de direcciones al navegar el calendario de
una temporada pasada en proballers.com.

## Estructura del proyecto

```
proa-predictor/
├── config.py                  # toda la configuración centralizada
├── pipeline.py                 # orquestador end-to-end
├── db/
│   ├── models.py               # esquema SQLAlchemy (equipos, partidos, stats, predicciones)
│   └── database.py             # conexión (SQLite local / Postgres en producción)
├── scraper/
│   ├── proballers_scraper.py   # scraping de calendario y boxscores
│   └── ingest.py                # vuelca lo scrapeado en la BD
├── features/
│   ├── elo.py                   # sistema de rating Elo
│   └── feature_engineering.py   # construcción del dataset de entrenamiento
├── models/
│   ├── train_model.py           # entrena clasificador + regresor (XGBoost)
│   └── predict.py               # predicciones para partidos pendientes
├── charts/
│   └── visualizations.py        # gráficos de análisis (Elo, importancia de features...)
└── scripts/
    └── github_actions_example.yml  # automatización tras cada jornada
```

## Cómo se evita el data leakage

Cada feature de un partido se calcula usando **solo** información anterior
a ese partido (medias móviles, Elo pre-partido, días de descanso desde el
partido anterior). El propio boxscore del partido a predecir nunca entra
en sus propias features. La validación del modelo usa un **split
temporal** (se entrena con los primeros partidos de la temporada y se
valida con los últimos), no aleatorio, para simular cómo se usará en
producción: predecir la jornada siguiente con lo que se sabe hasta hoy.

## Automatización ("al acabar la jornada, actualizar")

Copia `scripts/github_actions_example.yml` a `.github/workflows/pipeline.yml`
en tu repo. Correrá `python pipeline.py` automáticamente cada domingo y
lunes por la noche (ajusta el cron a como calcen las jornadas de la Pro A),
y también se puede lanzar a mano desde la pestaña "Actions" de GitHub.

Si migras la base de datos a Supabase/Postgres (recomendado para cuando
conectes esto con la app en Vercel), define `DATABASE_URL` como secreto en
GitHub y todo el código sigue funcionando igual — solo cambia la connection
string en `config.py`.

## Próximos pasos (roadmap sugerido)

1. **Correr el pipeline localmente** y revisar que el scraping funciona
   contra el HTML real de Proballers — las tablas se parsean con
   `pandas.read_html()`, que es robusto a cambios de estilo, pero si
   Proballers cambia los nombres de columna habrá que ajustar los `.get()`
   en `proballers_scraper.py`.
2. Añadir **datos de lesiones/bajas** (el factor más predictivo y más
   difícil de automatizar — probablemente haya que introducirlo a mano al
   principio, con la ayuda de tu hermano).
3. Añadir métricas avanzadas a nivel de jugador (PER/BPM simplificado) si
   se quiere capturar el impacto de bajas concretas, no solo la ausencia.
4. Sustituir SQLite por Supabase/Postgres cuando construyas la app en
   Vercel, y montar un endpoint (FastAPI o funciones serverless de Vercel)
   que sirva las predicciones guardadas en `predictions`.
5. Backtesting más riguroso: walk-forward validation partido a partido en
   vez de un único split, para tener intervalos de confianza reales sobre
   el accuracy.

## Nota legal

Proballers ofrece explícitamente acceso a sus datos vía API para clubes,
ligas y federaciones. Este scraper está pensado para uso personal/analítico
sin fines comerciales. Si el proyecto se convierte en algo público a gran
escala, merece la pena revisar sus términos de uso o contactar con ellos
para acceso vía API oficial en vez de scraping.
