# Parche: logos, nombres, local/visitante, previews y % de tiro

Copia el contenido de este zip sobre tu repo (respeta las carpetas) y luego:

    python scripts/patch_stats_ts.py     # parchea proa-web/lib/stats.ts
    python reset_database.py             # los partidos guardados tienen local/visitante invertido
    python pipeline.py

Archivos:
- config.py                                  (TEAM_NAME_OVERRIDES)
- scraper/realgm_scraper.py                  (local/visitante por slug, nombres, equipos sin duplicar)
- proa-web/lib/team-logo.tsx                 (logos de RealGM + iniciales de respaldo)
- proa-web/app/partidos/[gameId]/page.tsx    (sin datos de la temporada pasada en el preview)
- proa-web/app/partidos/[gameId]/boxscore-panel.tsx  (% T2, % T3, % TL)
- scripts/patch_stats_ts.py                  (cambia stats.ts; no se incluye entero por su tamaño)

Si usas Supabase, vacia tambien sus tablas antes de reingerir.
