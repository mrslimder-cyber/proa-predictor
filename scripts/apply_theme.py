"""
Aplica el rework visual: importa theme.css en layout.tsx, agranda los logos
(x1.3) y cambia los colores de los graficos antiguos a la paleta alemana.
Uso (raiz del repo):  python scripts/apply_theme.py
Seguro: copia .bak y, si algun fragmento no aparece exactamente una vez, no toca nada.
"""
import sys
from pathlib import Path

def load(p):
    p = Path(p)
    if not p.exists():
        sys.exit(f"No encuentro {p}. Ejecuta desde la raiz del repo.")
    return p, p.read_text(encoding="utf-8").replace("\r\n", "\n")

def once(t, old, new, label):
    if t.count(old) != 1:
        sys.exit(f"[ERROR] '{label}': esperaba 1 coincidencia y hay {t.count(old)}. No se ha modificado nada.")
    return t.replace(old, new)

p_lay, lay = load("proa-web/app/layout.tsx")
p_logo, logo = load("proa-web/lib/team-logo.tsx")
charts = [load("proa-web/app/evolucion/evolution-charts.tsx"),
          load("proa-web/app/temporadas/[season]/equipos/[teamId]/team-charts.tsx")]
if "theme.css" in lay:
    sys.exit("Parece que ya estaba aplicado. No hago nada.")

lay = once(lay, 'import "./globals.css";\n', 'import "./globals.css";\nimport "./theme.css";\n', "import theme.css")
logo = once(logo, "  size = 24,\n}: {", "  size: baseSize = 24,\n}: {", "firma TeamLogo")
logo = once(logo, "  const [failed, setFailed] = useState(false);\n  const url = teamLogoUrl(teamId);\n",
            "  const size = Math.round(baseSize * 1.3); // logos un 30% mas grandes en toda la web\n  const [failed, setFailed] = useState(false);\n  const url = teamLogoUrl(teamId);\n", "cuerpo TeamLogo")

COLORS = {"#ff8a2b": "#FFCE00", "#46cf8b": "#FFCE00", "#1a2028": "#18181d", "#29323d": "#2a2a31", "#98a3ad": "#a1a1ab"}
new_charts = []
for p, t in charts:
    for a, b in COLORS.items():
        t = t.replace(a, b)
    new_charts.append((p, t))

for p, t in [(p_lay, lay), (p_logo, logo)] + new_charts:
    p.with_suffix(p.suffix + ".bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    p.write_text(t, encoding="utf-8")
    print(f"OK: {p}")
