"""
Aplica el cambio "formulas de Dean Oliver" a tres archivos existentes:

  1) scraper/ingest.py               -> recalcula los Four Factors con features/formulas.py
  2) features/feature_engineering.py -> elimina estimate_possessions (sin uso, formula antigua)
  3) proa-web/lib/stats.ts           -> posesiones de Oliver (media de ambos equipos)
                                        + FT rate = FTM/FGA

Uso (desde la raiz del repo, con features/formulas.py ya copiado):
    python scripts/apply_oliver_formulas.py

Seguro: hace copia .bak de cada archivo y, si algun fragmento esperado no
aparece EXACTAMENTE una vez, no modifica NINGUN archivo. Si lo ejecutas dos
veces, avisa de que ya estaba aplicado.
"""
import sys
from pathlib import Path


def sub_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.exit(f"[ERROR] '{label}': esperaba 1 coincidencia y hay {n}. No se ha modificado nada.")
    return text.replace(old, new)


def sub_twice(text, old, new, label):
    n = text.count(old)
    if n != 2:
        sys.exit(f"[ERROR] '{label}': esperaba 2 coincidencias y hay {n}. No se ha modificado nada.")
    return text.replace(old, new)


def load(path):
    p = Path(path)
    if not p.exists():
        sys.exit(f"No encuentro {p}. Ejecuta el script desde la raiz del repo.")
    return p, p.read_text(encoding="utf-8").replace("\r\n", "\n")


if not Path("features/formulas.py").exists():
    sys.exit("Falta features/formulas.py. Copialo antes de ejecutar este script.")

# ---------------------------------------------------------------- ingest.py
p_ing, ing = load("scraper/ingest.py")
p_fe, fe = load("features/feature_engineering.py")
p_ts, ts = load("proa-web/lib/stats.ts")

if "apply_four_factors" in ing or "gamePossessions" in ts:
    sys.exit("Parece que el parche ya estaba aplicado. No hago nada.")

ing = sub_once(
    ing,
    "from scraper.bridge import backfill_new_teams\n",
    "from scraper.bridge import backfill_new_teams\nfrom features.formulas import apply_four_factors\n",
    "import en ingest.py",
)
ing = sub_once(
    ing,
    "            for ts in box[\"team_stats\"]:\n                session.merge(TeamGameStats(game_id=g[\"game_id\"], **ts))\n",
    "            # Four Factors siempre con las formulas de Oliver (features/formulas.py),\n"
    "            # no con lo que publique RealGM (escala y definicion de FTR distintas).\n"
    "            apply_four_factors(box[\"team_stats\"])\n"
    "            for ts in box[\"team_stats\"]:\n                session.merge(TeamGameStats(game_id=g[\"game_id\"], **ts))\n",
    "merge de team_stats en ingest.py",
)

# ------------------------------------------------- feature_engineering.py
fe = sub_once(
    fe,
    'def estimate_possessions(row: dict) -> float:\n'
    '    """Posesiones ≈ FGA - ORB + TOV + 0.44*FTA (fórmula estándar de Dean Oliver)."""\n'
    '    fga = row["fg2_att"] + row["fg3_att"]\n'
    '    return fga - row["oreb"] + row["tov"] + 0.44 * row["ft_att"]\n\n\n',
    "",
    "estimate_possessions en feature_engineering.py",
)

# ----------------------------------------------------------- stats.ts
ts = sub_once(
    ts,
    "function estimatePossessions(s: {\n"
    "  fg2_att: number | null; fg3_att: number | null;\n"
    "  oreb: number | null; tov: number | null; ft_att: number | null;\n"
    "}): number | null {\n"
    "  if (s.fg2_att == null || s.fg3_att == null || s.oreb == null || s.tov == null || s.ft_att == null) return null;\n"
    "  return (s.fg2_att + s.fg3_att) - s.oreb + s.tov + 0.44 * s.ft_att;\n"
    "}\n",
    "/**\n"
    " * Posesiones propias estimadas, formula completa de Dean Oliver:\n"
    " *   FGA + 0.4*FTA - 1.07*(ORB/(ORB + DRB rival))*(FGA - FGM) + TOV\n"
    " * Mismo calculo que features/formulas.py (_own_possessions).\n"
    " */\n"
    "function ownPossessions(own: TeamGameStats, opp: TeamGameStats): number | null {\n"
    "  if (\n"
    "    own.fg2_made == null || own.fg2_att == null || own.fg3_made == null || own.fg3_att == null ||\n"
    "    own.ft_att == null || own.oreb == null || own.tov == null || opp.dreb == null\n"
    "  ) return null;\n"
    "  const fga = own.fg2_att + own.fg3_att;\n"
    "  const fgm = own.fg2_made + own.fg3_made;\n"
    "  const orbShare = own.oreb + opp.dreb > 0 ? own.oreb / (own.oreb + opp.dreb) : 0;\n"
    "  return fga + 0.4 * own.ft_att - 1.07 * orbShare * (fga - fgm) + own.tov;\n"
    "}\n\n"
    "/** Posesiones del partido: media de la estimacion de ambos equipos (misma cifra para los dos). */\n"
    "export function gamePossessions(a: TeamGameStats, b: TeamGameStats): number | null {\n"
    "  const pa = ownPossessions(a, b);\n"
    "  const pb = ownPossessions(b, a);\n"
    "  return pa == null || pb == null ? null : (pa + pb) / 2;\n"
    "}\n",
    "estimatePossessions en stats.ts",
)
ts = sub_once(
    ts,
    "    for (const [own, opp] of [[a, b], [b, a]] as const) {\n"
    "      const ownPoss = estimatePossessions(own);\n"
    "      const oppPoss = estimatePossessions(opp);\n"
    "      if (ownPoss == null || oppPoss == null) continue;\n"
    "      const e = ensure(own.team_id);\n"
    "      e.games += 1;\n"
    "      e.pts += own.pts ?? 0;\n"
    "      e.poss += ownPoss;\n"
    "      e.oppPts += opp.pts ?? 0;\n"
    "      e.oppPoss += oppPoss;\n"
    "    }\n",
    "    const poss = gamePossessions(a, b);\n"
    "    if (poss == null) continue;\n"
    "    for (const [own, opp] of [[a, b], [b, a]] as const) {\n"
    "      const e = ensure(own.team_id);\n"
    "      e.games += 1;\n"
    "      e.pts += own.pts ?? 0;\n"
    "      e.poss += poss;\n"
    "      e.oppPts += opp.pts ?? 0;\n"
    "      e.oppPoss += poss;\n"
    "    }\n",
    "bucle de getSeasonAdvancedStats",
)
# Four Factors: FT rate = FTM / FGA
ts = sub_once(
    ts,
    "const acc = new Map<number, { games: number; fgm: number; fga: number; fg3m: number; fta: number; tov: number; oreb: number; oppDreb: number }>();",
    "const acc = new Map<number, { games: number; fgm: number; fga: number; fg3m: number; ftm: number; fta: number; tov: number; oreb: number; oppDreb: number }>();",
    "tipo acc de getSeasonFourFactors",
)
ts = sub_once(
    ts,
    "{ games: 0, fgm: 0, fga: 0, fg3m: 0, fta: 0, tov: 0, oreb: 0, oppDreb: 0 }",
    "{ games: 0, fgm: 0, fga: 0, fg3m: 0, ftm: 0, fta: 0, tov: 0, oreb: 0, oppDreb: 0 }",
    "inicializacion acc de getSeasonFourFactors",
)
ts = sub_once(
    ts,
    "if (own.fg2_att == null || own.fg3_att == null || own.ft_att == null || own.tov == null || own.oreb == null || opp.dreb == null) {",
    "if (own.fg2_att == null || own.fg3_att == null || own.ft_made == null || own.ft_att == null || own.tov == null || own.oreb == null || opp.dreb == null) {",
    "guarda de getSeasonFourFactors",
)
ts = sub_once(ts, "      e.fta += own.ft_att;\n", "      e.ftm += own.ft_made;\n      e.fta += own.ft_att;\n", "acumulador ftm")
ts = sub_once(ts, "      ftRate: e.fta / e.fga,\n", "      ftRate: e.ftm / e.fga,\n", "ftRate")

# ------------------------------------------------------------- escritura
for p, new in ((p_ing, ing), (p_fe, fe), (p_ts, ts)):
    p.with_suffix(p.suffix + ".bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.write_text(new, encoding="utf-8")
    print(f"OK: {p} parcheado (copia en {p.name}.bak)")
