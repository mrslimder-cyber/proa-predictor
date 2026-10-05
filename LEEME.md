# Scrapeo manual de boxscores desde PDF (Liveticker)

Para partidos sin boxscore en RealGM: imprime/guarda como PDF la página del
Liveticker de 2basketballbundesliga.de y impórtalo con el script.

## Archivos de este zip (copia sobre tu repo)

    requirements.txt              (nuevo: añade pdfplumber)
    scraper/liveticker_pdf.py     (nuevo)
    scraper/ingest.py             (modificado: no degrada un partido 'final' a 'scheduled')

## Instalación

    pip install -r requirements.txt

## Comandos

    # 1) Probar sin escribir nada (muestra partido encontrado, emparejamientos y marcador)
    python -m scraper.liveticker_pdf partido.pdf --dry-run

    # 2) Importar un PDF
    python -m scraper.liveticker_pdf partido.pdf

    # 3) Importar varios PDFs o una carpeta entera
    python -m scraper.liveticker_pdf pdfs/
    python -m scraper.liveticker_pdf a.pdf b.pdf "pdfs/*.pdf"

    # 4) Reemplazar un partido que ya tenía stats guardadas
    python -m scraper.liveticker_pdf partido.pdf --force

    # 5) Crear el partido si no existe en la BD (los dos equipos sí deben existir)
    python -m scraper.liveticker_pdf partido.pdf --create

Después, para reentrenar/predecir/regenerar claves con los datos nuevos:

    python pipeline.py

(si usas Supabase, apunta DATABASE_URL a Supabase antes de importar.)

## Cómo se emparejan nombres

- Equipos: busca partidos de la BD a ±2 días de la fecha del PDF y elige el que
  mejor encaja con los dos equipos (ignora acentos, espacios, ae/oe/ue y tolera
  letras distintas). Local/visitante lo decide la BD.
- Jugadores: se emparejan con los ya guardados de ese equipo (mismo player_id
  que RealGM). Tolera 1 letra distinta, CJ/C.J., Jr/Sr y apellidos recortados.
  Si no hay coincidencia, crea un id negativo estable.
- Lo que no sea exacto se imprime como [~] (emparejado) o [+] (id nuevo): revísalo.
- Si algo no cuadra (puntos de jugadores vs total, 2*T2+3*T3+TL vs puntos) sale [AVISO].

## Notas

- Un partido que ya tiene stats se salta (usa --force para reemplazar).
- El script no guarda jugadores con 00:00 y sin estadísticas.
- Four Factors se guardan en escala 0-1 (igual que scripts/backfill_four_factors.py).
- Probado con el PDF de OrangeAcademy 85-94 Kirchheim (lectura y emparejamiento);
  la escritura en BD no se pudo probar en el entorno de desarrollo: usa --dry-run primero.
