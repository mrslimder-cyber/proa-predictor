# Cambios: migración de Proballers/2basketballbundesliga.de a RealGM

## 1. Archivos de este zip (copia pisando los que ya tienes en el repo)

```
config.py                                  (modificado)
requirements.txt                           (modificado -- sin playwright)
reset_database.py                          (nuevo)
CAMBIOS.md                                 (este archivo, no hace falta commitearlo)
scraper/realgm_scraper.py                  (nuevo -- sustituye a proballers_scraper.py,
                                             bundesliga_scraper.py y live_boxscore_scraper.py)
scraper/ingest.py                          (modificado)
scraper/bridge.py                          (modificado -- backfill deshabilitado, ver cabecera)
.github/workflows/pipeline.yml             (modificado -- sin paso de Playwright)
scripts/github_actions_example.yml         (modificado -- igual que el anterior)
README.md                                  (modificado)
proa-web/app/layout.tsx                    (modificado -- footer "Datos vía RealGM")
```

`pipeline.py`, `db/models.py`, `features/*`, `models/*`, `charts/*`, el resto de
`proa-web/` y `supabase/schema.sql` **no cambian** -- el esquema de datos es el
mismo, solo cambia de dónde se rellena.

## 2. Archivos a ELIMINAR de tu repo (ya no los usa nada)

```
scraper/proballers_scraper.py
scraper/bundesliga_scraper.py
scraper/live_boxscore_scraper.py
inspect_block.py
```

`inspect_block.py` importaba directamente de `scraper.proballers_scraper` y de
`config.season_calendar_url` (ambos eliminados), así que dejaría de funcionar
igualmente si no lo borras.

`diagnose_home_win_balance.py` y `test/seed_and_test.py` **no se tocan** --
no dependen de ninguna de las fuentes de scraping, solo de `features/` y
`db/` directamente.

Comando rápido para borrarlos:

```bash
git rm scraper/proballers_scraper.py scraper/bundesliga_scraper.py scraper/live_boxscore_scraper.py inspect_block.py
```

## 3. ⚠️ Antes de reingerir: vacía la base de datos

Los ids de equipo y de partido de RealGM son números **distintos** a los que
ya tenías guardados desde Proballers. Si lanzas el pipeline nuevo sin vaciar
antes, te va a crear equipos duplicados (mismo club, dos ids distintos) y vas
a partir en dos la serie de Elo/medias móviles de cada equipo.

```bash
python reset_database.py
```

Si usas Supabase en producción, corre el equivalente ahí (TRUNCATE de todas
las tablas en el SQL Editor, o apunta `DATABASE_URL` a tu Supabase antes de
correr `reset_database.py`, que es agnóstico al motor).

## 4. Pasos para aplicar todo

```bash
# 1. Copia los archivos de este zip sobre tu repo (pisa los que coincidan)
# 2. Borra los 4 archivos obsoletos listados arriba
pip install -r requirements.txt        # por si acaso, ya no pide playwright
python reset_database.py               # vacía la BD local (o la de Supabase)
python pipeline.py                     # reingiere todo desde RealGM + entrena + predice
```

La primera ingesta histórica (4-5 temporadas, día a día) puede tardar bastante
más que antes porque RealGM no expone un calendario de temporada en una sola
página verificada -- se recorre día a día (ver cabecera de
`scraper/realgm_scraper.py`). Las siguientes ejecuciones vuelven a ser
rápidas porque solo se descargan partidos/boxscores nuevos.

## 5. Qué NO está resuelto todavía

- **`scraper/bridge.py` (partidos puente para equipos ascendidos/descendidos)**
  queda deshabilitado: no hay aún una forma verificada de leer en RealGM el
  calendario de la temporada anterior de un equipo nuevo en otra liga. Un
  equipo nuevo simplemente se queda sin predicción hasta acumular
  `MIN_GAMES_FOR_FEATURES` partidos reales de Pro A (ver cabecera del
  archivo para cómo retomarlo).
- El parseo de `scraper/realgm_scraper.py` está verificado contra un partido
  real concreto, no contra cientos -- revisa los avisos al principio del
  archivo (orden local/visitante, rango de fechas de temporada, detección de
  la fila de totales de equipo) en tu primera ejecución grande, igual que ya
  hacía el proyecto con los avisos de Proballers.
