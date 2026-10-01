"""
Aplica el cambio "sin fallback a la temporada anterior" a proa-web/lib/stats.ts
sin tener que reemplazar todo el archivo.

Uso (desde la raiz del repo):
    python scripts/patch_stats_ts.py

Hace copia de seguridad en proa-web/lib/stats.ts.bak y falla (sin tocar nada)
si alguno de los fragmentos esperados no se encuentra exactamente una vez.
Si lo ejecutas dos veces, la segunda avisa de que ya estaba aplicado.
"""
import re
import sys
from pathlib import Path

PATH = Path("proa-web/lib/stats.ts")
if not PATH.exists():
    sys.exit(f"No encuentro {PATH}. Ejecuta el script desde la raiz del repo.")

src = PATH.read_text(encoding="utf-8").replace("\r\n", "\n")

if "isFallbackSeason" not in src:
    sys.exit("Parece que el parche ya estaba aplicado (no queda 'isFallbackSeason'). No hago nada.")


def sub_once(pattern, repl, text, flags=0, label=""):
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != 1:
        sys.exit(f"[ERROR] '{label}': esperaba 1 coincidencia y hay {n}. No se ha modificado nada.")
    return new


# 1) Tipo MatchupTeamSummary
src = sub_once(
    r"  season: string;[^\n]*\n  isFallbackSeason: boolean;[^\n]*\n",
    "  season: string;\n",
    src, label="tipo MatchupTeamSummary",
)

# 2) Cabecera de buildTeamSummary (todo hasta 'const gameIds')
src = sub_once(
    r"async function buildTeamSummary\(.*?\n(?=  const gameIds = games\.map\(\(g\) => g\.id\);\n  const opponentIds)",
    (
        "async function buildTeamSummary(\n"
        "  season: string,\n"
        "  team: Team,\n"
        "  beforeDate: string\n"
        "): Promise<MatchupTeamSummary> {\n"
        "  // Solo partidos de ESTA temporada anteriores al partido: sin fallback a\n"
        "  // la temporada pasada (un equipo sin partidos se muestra con 0 jugados).\n"
        "  const games = await getFinishedTeamGames(season, team.id, beforeDate);\n\n"
    ),
    src, flags=re.DOTALL, label="cabecera buildTeamSummary",
)

# 3) return de buildTeamSummary
src = sub_once(r"    isFallbackSeason,\n(    record: \{ wins, losses \},)", r"\1", src, label="return buildTeamSummary")

# 4) getMatchupPreview
src = sub_once(
    r"const \[teamById, \{ data: predictions \}, allSeasonsDesc\] = await Promise\.all\(\[",
    "const [teamById, { data: predictions }] = await Promise.all([",
    src, label="Promise.all getMatchupPreview",
)
src = sub_once(r"(      \.limit\(1\),\n)    getSeasons\(\),\n(  \]\);)", r"\1\2", src, label="getSeasons() en getMatchupPreview")
src = sub_once(r"buildTeamSummary\(game\.season, homeTeam, cutoffDate, allSeasonsDesc\)",
               "buildTeamSummary(game.season, homeTeam, cutoffDate)", src, label="llamada home")
src = sub_once(r"buildTeamSummary\(game\.season, awayTeam, cutoffDate, allSeasonsDesc\)",
               "buildTeamSummary(game.season, awayTeam, cutoffDate)", src, label="llamada away")

PATH.with_suffix(".ts.bak").write_text(PATH.read_text(encoding="utf-8"), encoding="utf-8")
PATH.write_text(src, encoding="utf-8")
print("OK: proa-web/lib/stats.ts parcheado (copia en stats.ts.bak).")
