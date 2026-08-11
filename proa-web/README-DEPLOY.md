# Desplegar ProA Predictor en Vercel

Este `proa-web/` es SOLO el frontend (lo que ve el usuario). El pipeline en
Python (scraping + modelo) sigue viviendo en `proa-predictor/` y corriendo
en tu ordenador o en GitHub Actions — Vercel no ejecuta ese código, solo
muestra lo que ya está guardado en la base de datos.

```
Python (pipeline.py) --escribe--> Supabase (Postgres) --lee--> Next.js en Vercel
```

## 1. Crear la base de datos en Supabase (gratis)

1. Ve a https://supabase.com, crea cuenta y un proyecto nuevo.
2. Entra en el proyecto -> **SQL Editor** -> pega el contenido de
   `supabase/schema.sql` -> Run. Esto crea las tablas.
3. Ve a **Project Settings -> API** y copia dos valores:
   - `Project URL`
   - `anon public key`

## 2. Conectar el pipeline de Python a Supabase

1. En `proa-predictor/`, copia `.env.example` a `.env`.
2. En **Project Settings -> Database -> Connection string** de Supabase,
   copia la cadena "URI" y pégala como `DATABASE_URL` en tu `.env`:
   ```
   DATABASE_URL=postgresql+psycopg2://postgres:TU-PASSWORD@db.xxxx.supabase.co:5432/postgres
   ```
3. Instala el driver de Postgres: `pip install psycopg2-binary`
4. Corre `python pipeline.py` una vez para comprobar que escribe en Supabase
   (mira las tablas desde el Table Editor de Supabase).

## 3. Subir el código a GitHub

```bash
cd proa-predictor
git init
git add .
git commit -m "proa predictor inicial"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/proa-predictor.git
git push -u origin main
```

Haz lo mismo con `proa-web/` en otro repo (o como subcarpeta del mismo,
Vercel te deja elegir el "Root Directory").

## 4. Automatizar el pipeline con GitHub Actions

1. Copia `scripts/github_actions_example.yml` a
   `.github/workflows/pipeline.yml` en el repo de `proa-predictor`.
2. En GitHub -> Settings -> Secrets and variables -> Actions, añade el
   secreto `DATABASE_URL` con la misma cadena de Supabase.
3. Así, cada vez que se juegue una jornada, GitHub corre el pipeline solo
   y actualiza Supabase — sin que tengas que hacer nada a mano.

## 5. Desplegar el frontend en Vercel

1. Ve a https://vercel.com -> **Add New -> Project** -> importa el repo de
   `proa-web`.
2. En **Environment Variables**, añade:
   - `NEXT_PUBLIC_SUPABASE_URL` = el Project URL de Supabase
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = la anon key de Supabase
3. Deploy. En 1-2 minutos tienes una URL tipo `proa-predictor.vercel.app`.

Como todavía no hay partidos de la temporada, la web se verá con el
mensaje de "todavía no hay predicciones" — es el comportamiento esperado.
En cuanto el pipeline meta el primer partido en Supabase, la página se
llena sola (se refresca automáticamente cada 5 minutos).

## Novedades de esta versión

- **`/temporadas`**: elige cualquier temporada histórica (según lo que haya
  en `games.season`) y verás la clasificación real (V-D, PF, PC, +/-),
  calculada a partir de los partidos con `status = 'final'`.
- En esa misma página: **líderes de la temporada** — puntos por partido
  (equipos y jugadores, mínimo 3 partidos jugados) y % de tiros libres
  (equipos y jugadores, con un mínimo de intentos para evitar rankings
  con muestras minúsculas).
- **`/temporadas/[temporada]/equipos/[id]`**: al elegir un equipo aparecen
  sus medias de la temporada, dos gráficos (puntos anotados vs. recibidos
  por jornada, y media de puntos por jugador), el top 3 de puntos, rebotes,
  asistencias y % de tiros libres, y la plantilla completa con las medias
  de cada jugador.
- Estas páginas usan las tablas `team_game_stats` y `player_game_stats`,
  que no tienen RLS activado en `schema.sql` (por eso son legibles con la
  `anon key` sin política adicional). Si quieres reforzarlo, puedes
  activar RLS y añadir una política de lectura pública igual que en
  `teams`/`games`, sin que cambie nada en el código del frontend.

## Probar en local antes de desplegar (opcional)

```bash
cd proa-web
npm install
cp .env.example .env.local   # rellena con tus credenciales de Supabase
npm run dev
```
Abre http://localhost:3000
