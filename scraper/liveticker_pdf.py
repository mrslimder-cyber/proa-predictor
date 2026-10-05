"""
scraper/liveticker_pdf.py

Importa a la BD el boxscore de un partido a partir del PDF del "Liveticker"
de 2basketballbundesliga.de (el que se imprime desde el navegador). Pensado
como RESPALDO para los partidos cuyo boxscore RealGM no publica.

Uso:
    python -m scraper.liveticker_pdf partido.pdf
    python -m scraper.liveticker_pdf carpeta_con_pdfs/ otro.pdf
    python -m scraper.liveticker_pdf partido.pdf --dry-run    # solo muestra, no escribe
    python -m scraper.liveticker_pdf partido.pdf --force      # reemplaza stats ya guardadas
    python -m scraper.liveticker_pdf partido.pdf --create     # crea el partido si no existe en la BD
    python -m scraper.liveticker_pdf partido.pdf --game-id 525443   # fuerza el partido (id de la BD)

Como evita problemas con nombres "casi iguales":
  - EQUIPOS: no se compara texto exacto. Se buscan los partidos de la BD en
    +-2 dias de la fecha del PDF y se elige el que mejor encaja con los DOS
    equipos a la vez (normalizando acentos, ae/oe/ue, espacios y usando
    similitud difusa). Local/visitante lo decide la BD, no el orden del PDF.
  - JUGADORES: se emparejan por similitud con los jugadores ya guardados de
    ESE equipo (misma persona -> mismo player_id que en RealGM). Tolera una
    letra distinta, "CJ" vs "C.J.", sufijos Jr/Sr, apellidos compuestos
    recortados, etc. Cada id de la BD solo se asigna a un jugador del PDF.
    Si no hay ningun candidato razonable, se crea un id negativo estable.
  - Todo emparejamiento no exacto se imprime para que lo revises.
"""
import argparse
import re
import sys
import unicodedata
import zlib
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

MIN_TEAM_SIM = 0.60        # similitud minima por equipo para aceptar un partido
PLAYER_SIM_SAME_TEAM = 0.80
PLAYER_SIM_OTHER_TEAM = 0.93   # fichajes: solo se acepta casi identico
DATE_TOLERANCE_DAYS = 2

# --------------------------------------------------------------------------
# Texto del PDF
# --------------------------------------------------------------------------
_MADE = r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*%"
_STATS = (
    rf"{_MADE}\s+{_MADE}\s+{_MADE}\s+{_MADE}\s+"          # 2P 3P FG FT (made-att-pct)
    r"(-?\d+)\s+(\d+)\s+"                                   # P AS
    r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s+"                     # R: O-D-T
    r"(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)"              # F BL ST TO EF
)
PLAYER_RE = re.compile(rf"^#?(\d+)\s+(.+?)\s+(\d{{1,3}}):(\d{{2}})\s+{_STATS}\s*$")
TEAM_RE = re.compile(rf"^(?!#)(.+?)\s+{_STATS}\s*$")
DATE_RE = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
SCORE_RE = re.compile(r"^(\d{1,3})\s*-\s*(\d{1,3})$")


def extract_text(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except ImportError:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def _stats_from_groups(g: list[str]) -> dict:
    n = [int(x) for x in g]
    return {
        "fg2_made": n[0], "fg2_att": n[1],
        "fg3_made": n[3], "fg3_att": n[4],
        "ft_made": n[9], "ft_att": n[10],
        "pts": n[12], "ast": n[13],
        "oreb": n[14], "dreb": n[15], "reb": n[16],
        "pf": n[17], "blk": n[18], "stl": n[19], "tov": n[20],
        "valuation": n[21],
    }


def parse_text(text: str) -> dict:
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]

    date = None
    score = None
    for l in lines:
        if date is None:
            m = DATE_RE.search(l)
            if m:
                date = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if score is None:
            m = SCORE_RE.match(l)
            if m:
                score = (int(m.group(1)), int(m.group(2)))
    if date is None:
        raise ValueError("No encuentro la fecha (dd.mm.aaaa) en el PDF.")

    headers = [i for i, l in enumerate(lines) if l.upper().startswith("SPIELER")]
    if len(headers) != 2:
        raise ValueError(f"Esperaba 2 tablas de jugadores (SPIELER) y hay {len(headers)}.")

    # Tabla resumen de equipos (antes de la primera tabla de jugadores)
    team_rows = []
    for l in lines[: headers[0]]:
        m = TEAM_RE.match(l)
        if m:
            team_rows.append((m.group(1).strip(), _stats_from_groups(list(m.groups()[1:]))))

    teams = []
    for k, h in enumerate(headers):
        name = lines[h - 1]
        end = headers[k + 1] - 1 if k + 1 < len(headers) else len(lines)
        players = []
        for l in lines[h + 1:end]:
            if l.lower().startswith("gesamt"):
                break
            m = PLAYER_RE.match(l)
            if not m:
                continue
            groups = m.groups()
            st = _stats_from_groups(list(groups[4:]))
            st.update({
                "name": groups[1].strip(),
                "number": int(groups[0]),
                "minutes": round(int(groups[2]) + int(groups[3]) / 60, 1),
                "_secs": int(groups[2]) * 60 + int(groups[3]),
            })
            players.append(st)
        teams.append({"name": name, "players": players, "totals": None})

    # Asignar cada fila de totales al equipo cuyo nombre mas se parece
    for t in teams:
        best = max(team_rows, key=lambda r: name_sim(t["name"], r[0]), default=None)
        if best and name_sim(t["name"], best[0]) >= MIN_TEAM_SIM:
            t["totals"] = best[1]
    if any(t["totals"] is None for t in teams):
        if len(team_rows) == 2:           # respaldo: por orden de aparicion
            teams[0]["totals"], teams[1]["totals"] = team_rows[0][1], team_rows[1][1]
        else:
            raise ValueError("No he podido leer la tabla de totales por equipo.")
    for k, t in enumerate(teams):
        t["score"] = t["totals"]["pts"]
        if score and t["score"] is None:
            t["score"] = score[k]

    return {"date": date, "teams": teams, "header_score": score}


def validate(parsed: dict) -> list[str]:
    """Comprobaciones de coherencia: si algo no cuadra, el PDF se ha leido mal."""
    w = []
    hs = parsed["header_score"]
    for k, t in enumerate(parsed["teams"]):
        if not t["players"]:
            w.append(f"{t['name']}: no se ha leido ningun jugador.")
            continue
        s = sum(p["pts"] for p in t["players"])
        if s != t["totals"]["pts"]:
            w.append(f"{t['name']}: los puntos de los jugadores suman {s} y el total del equipo es {t['totals']['pts']}.")
        if hs and hs[k] != t["totals"]["pts"]:
            w.append(f"{t['name']}: marcador de cabecera {hs[k]} != total {t['totals']['pts']}.")
        tt = t["totals"]
        if tt["fg2_made"] * 2 + tt["fg3_made"] * 3 + tt["ft_made"] != tt["pts"]:
            w.append(f"{t['name']}: 2*T2 + 3*T3 + TL no es igual a los puntos.")
    return w


# --------------------------------------------------------------------------
# Normalizacion y similitud
# --------------------------------------------------------------------------
def _strip(s: str) -> str:
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def compact_team(s: str) -> str:
    s = _strip(s)
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def player_tokens(s: str) -> list[str]:
    s = _strip(s)
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9 ]", " ", s.replace(".", ""))
    return [t for t in s.split() if t not in _SUFFIXES]


def _sim(ca: str, cb: str) -> float:
    if not ca or not cb:
        return 0.0
    sm = SequenceMatcher(None, ca, cb)
    ratio = sm.ratio()
    m = sm.find_longest_match(0, len(ca), 0, len(cb))
    contain = m.size / min(len(ca), len(cb))
    return max(ratio, 0.95 * contain if m.size >= 6 else 0.0)


def _team_words(s: str) -> list[str]:
    s = _strip(s)
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u")):
        s = s.replace(a, b)
    return [w for w in re.split(r"[^a-z0-9]+", s) if len(w) >= 3]


def name_sim(a: str, b: str) -> float:
    """Similitud de nombres de equipo, 0..1. Combina el parecido del texto
    completo con el de palabras sueltas, para que un patrocinador distinto
    ('Kreisbau Kirchheim Knights' vs 'Bozic Estriche Knights Kirchheim')
    no impida emparejar al equipo."""
    whole = _sim(compact_team(a), compact_team(b))
    wa, wb = _team_words(a), _team_words(b)
    if not wa or not wb:
        return whole
    short, long_ = (wa, wb) if len(wa) <= len(wb) else (wb, wa)
    matched = sum(1 for w in short if max(_sim(w, x) for x in long_) >= 0.85)
    words = 0.95 * matched / len(short) if (matched >= 2 or len(short) == 1) else 0.0
    return max(whole, words)


def player_sim(a: str, b: str) -> float:
    ta, tb = player_tokens(a), player_tokens(b)
    if not ta or not tb:
        return 0.0
    full = _sim("".join(ta), "".join(tb))
    # mismo apellido (ultimo token) casi igual + misma inicial del nombre
    sur = _sim(ta[-1], tb[-1])
    if sur >= 0.85 and ta[0][0] == tb[0][0] and (len(ta) > 1 and len(tb) > 1):
        initial = len(ta[0]) == 1 or len(tb[0]) == 1      # "C. Anthony" vs "Cj Anthony"
        first = 1.0 if initial else _sim(ta[0], tb[0])
        full = max(full, min(0.97, 0.5 * sur + 0.5 * first))
    # un nombre es subconjunto del otro ("Juom Maker" vs "Juom Maker Bol Meen")
    sa, sb = set(ta), set(tb)
    if len(sa) >= 2 and len(sb) >= 2 and (sa <= sb or sb <= sa):
        full = max(full, 0.9)
    return min(full, 1.0)


def fallback_player_id(team_id: int, name: str) -> int:
    key = f"{team_id}:{''.join(player_tokens(name))}"
    return -(zlib.crc32(key.encode("utf-8")) % 2_000_000_000) - 1


# --------------------------------------------------------------------------
# Emparejamiento con la BD
# --------------------------------------------------------------------------
def find_game(session, parsed: dict, game_id: int | None = None):
    """Devuelve (game, [team_id_para_pdf0, team_id_para_pdf1], informe_candidatos).
    Si se pasa game_id se usa ese partido sin exigir parecido minimo de nombres
    (solo se decide la orientacion por el mejor encaje)."""
    from db.models import Game, Team

    if game_id is not None:
        g = session.get(Game, game_id)
        if g is None:
            return None, None, [(0, f"no existe ningun partido con id {game_id}")]
        names = {t.id: t.name for t in session.query(Team).all()}
        hn, an = names.get(g.home_team_id, ""), names.get(g.away_team_id, "")
        p0, p1 = parsed["teams"][0]["name"], parsed["teams"][1]["name"]
        direct = name_sim(p0, hn) + name_sim(p1, an)
        swapped = name_sim(p0, an) + name_sim(p1, hn)
        mapping = [g.home_team_id, g.away_team_id] if direct >= swapped else [g.away_team_id, g.home_team_id]
        return g, mapping, []

    d = parsed["date"]
    lo = d - timedelta(days=DATE_TOLERANCE_DAYS)
    hi = d + timedelta(days=DATE_TOLERANCE_DAYS + 1)
    games = session.query(Game).filter(Game.date >= lo, Game.date < hi).all()
    names = {t.id: t.name for t in session.query(Team).all()}
    p0, p1 = parsed["teams"][0]["name"], parsed["teams"][1]["name"]

    best, report = None, []
    for g in games:
        hn, an = names.get(g.home_team_id, ""), names.get(g.away_team_id, "")
        a = (name_sim(p0, hn), name_sim(p1, an))
        b = (name_sim(p0, an), name_sim(p1, hn))
        (pair, mapping) = (a, [g.home_team_id, g.away_team_id]) if sum(a) >= sum(b) \
            else (b, [g.away_team_id, g.home_team_id])
        score = sum(pair) - 0.01 * abs((g.date - d).days)
        report.append((score, f"{hn} - {an} ({g.date:%Y-%m-%d}) sim={pair[0]:.2f}/{pair[1]:.2f}"))
        if min(pair) >= MIN_TEAM_SIM and (best is None or score > best[0]):
            best = (score, g, mapping)
    report.sort(reverse=True)
    if best:
        return best[1], best[2], report
    return None, None, report


def resolve_team_ids_global(session, parsed: dict):
    """Para --create: busca cada equipo del PDF entre TODOS los equipos de la BD."""
    from db.models import Team
    teams = session.query(Team).all()
    out, used = [], set()
    for t in parsed["teams"]:
        cand = sorted(((name_sim(t["name"], x.name), x.id) for x in teams if x.id not in used), reverse=True)
        if not cand or cand[0][0] < MIN_TEAM_SIM:
            raise ValueError(f"No encuentro en la BD ningun equipo parecido a '{t['name']}'.")
        out.append(cand[0][1])
        used.add(cand[0][1])
    return out


def resolve_players(team_id: int, pdf_players: list[dict], known: dict[int, dict[int, str]]):
    """Asigna player_id a cada jugador del PDF. known: {team_id: {player_id: nombre}}."""
    own = known.get(team_id, {})
    others = {pid: n for tid, d in known.items() if tid != team_id for pid, n in d.items()}

    pairs = []
    for i, p in enumerate(pdf_players):
        for pid, n in own.items():
            s = player_sim(p["name"], n)
            if s >= PLAYER_SIM_SAME_TEAM:
                pairs.append((s, i, pid, n))
        for pid, n in others.items():
            s = player_sim(p["name"], n)
            if s >= PLAYER_SIM_OTHER_TEAM:
                pairs.append((s - 0.001, i, pid, n))
    pairs.sort(reverse=True)

    assigned, used_ids, notes = {}, set(), []
    for s, i, pid, n in pairs:
        if i in assigned or pid in used_ids:
            continue
        assigned[i] = pid
        used_ids.add(pid)
        if s < 0.999 and player_tokens(pdf_players[i]["name"]) != player_tokens(n):
            notes.append(f"  [~] '{pdf_players[i]['name']}' -> '{n}' (id {pid}, sim {s:.2f})")
    # Segunda pasada: mismo equipo, mismo apellido e inicial del nombre, y SOLO un
    # candidato posible por ambos lados ("Corey Hines Jr" vs "C.J. Hines").
    def surname(n):
        t = player_tokens(n)
        return t[-1] if t else ""

    def initial(n):
        t = player_tokens(n)
        return t[0][0] if t else ""

    free_ids = {pid: n for pid, n in own.items() if pid not in used_ids}
    pending = [i for i in range(len(pdf_players)) if i not in assigned]
    for i in pending:
        p = pdf_players[i]
        cands = [(pid, n) for pid, n in free_ids.items()
                 if pid not in used_ids and _sim(surname(p["name"]), surname(n)) >= 0.9
                 and initial(p["name"]) == initial(n)]
        same_surname_pdf = [j for j in pending if j not in assigned
                            and _sim(surname(pdf_players[j]["name"]), surname(p["name"])) >= 0.9]
        if len(cands) == 1 and len(same_surname_pdf) == 1:
            pid, n = cands[0]
            assigned[i] = pid
            used_ids.add(pid)
            notes.append(f"  [~?] '{p['name']}' -> '{n}' (id {pid}, mismo apellido e inicial: REVISAR)")

    for i, p in enumerate(pdf_players):
        if i not in assigned:
            pid = fallback_player_id(team_id, p["name"])
            assigned[i] = pid
            notes.append(f"  [+] '{p['name']}' sin coincidencia: id nuevo {pid}")
    return [assigned[i] for i in range(len(pdf_players))], notes


# --------------------------------------------------------------------------
# Four Factors (misma formula que scripts/backfill_four_factors.py, en 0-1)
# --------------------------------------------------------------------------
def four_factors(own: dict, opp: dict) -> dict:
    fgm, fga = own["fg2_made"] + own["fg3_made"], own["fg2_att"] + own["fg3_att"]
    fta, tov, oreb = own["ft_att"], own["tov"], own["oreb"]
    den = fga + 0.44 * fta + tov
    return {
        "efg_pct": (fgm + 0.5 * own["fg3_made"]) / fga if fga else None,
        "tov_pct": tov / den if den else None,
        "orb_pct": oreb / (oreb + opp["dreb"]) if (oreb + opp["dreb"]) > 0 else None,
        "ft_rate": fta / fga if fga else None,
    }


# --------------------------------------------------------------------------
# Importacion
# --------------------------------------------------------------------------
_TEAM_COLS = ("fg2_made", "fg2_att", "fg3_made", "fg3_att", "ft_made", "ft_att",
              "oreb", "dreb", "reb", "ast", "tov", "stl", "blk", "pf", "pts")
_PLAYER_COLS = ("minutes", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "valuation",
                "fg2_made", "fg2_att", "fg3_made", "fg3_att", "ft_made", "ft_att")


def _known_players(session) -> dict[int, dict[int, str]]:
    from db.models import PlayerGameStats
    known: dict[int, dict[int, str]] = {}
    rows = session.query(PlayerGameStats.team_id, PlayerGameStats.player_id,
                         PlayerGameStats.player_name).distinct().all()
    for tid, pid, name in rows:
        known.setdefault(tid, {})[pid] = name
    return known


def import_parsed(parsed: dict, dry_run=False, force=False, create=False, game_id=None) -> bool:
    from db.database import get_session, init_db
    from db.models import Game, PlayerGameStats, TeamGameStats

    init_db()
    warnings = validate(parsed)
    for w in warnings:
        print(f"  [AVISO] {w}")

    with get_session() as session:
        game, mapping, report = find_game(session, parsed, game_id)

        if game is None:
            if not create:
                print("  [ERROR] No hay ningun partido en la BD que encaje (fecha +-2 dias y los dos equipos).")
                for _, line in report[:5]:
                    print(f"     candidato: {line}")
                print("     Usa --create si el partido no esta en la BD.")
                return False
            mapping = resolve_team_ids_global(session, parsed)
            y, m = parsed["date"].year, parsed["date"].month
            season = f"{y}-{y + 1}" if m >= 7 else f"{y - 1}-{y}"
            gid = -(zlib.crc32(f"{parsed['date']:%Y%m%d}:{mapping[0]}:{mapping[1]}".encode()) % 2_000_000_000) - 1
            game = session.get(Game, gid)
            if game is None and not dry_run:
                # En el PDF el equipo de la izquierda es el local (convencion de la web).
                game = Game(id=gid, season=season, date=parsed["date"], home_team_id=mapping[0],
                            away_team_id=mapping[1], status="scheduled")
                session.add(game)
                session.flush()
                print(f"  [CREADO] partido nuevo id={gid} ({season})")

        if game is not None:
            print(f"  Partido en BD: id={game.id} {game.date:%Y-%m-%d} "
                  f"(home={game.home_team_id}, away={game.away_team_id})")
        home_id = game.home_team_id if game is not None else mapping[0]

        existing = 0
        if game is not None:
            existing = session.query(TeamGameStats).filter(TeamGameStats.game_id == game.id).count()
        if existing and not force:
            print("  [SKIP] ese partido ya tiene stats guardadas. Usa --force para reemplazarlas.")
            return False

        known = _known_players(session)
        by_team = {mapping[k]: parsed["teams"][k] for k in range(2)}
        ids = list(by_team)
        resolved = {}
        for tid, t in by_team.items():
            pids, notes = resolve_players(tid, t["players"], known)
            resolved[tid] = pids
            for n in notes:
                print(n)

        home_t = by_team[home_id]
        away_t = by_team[[i for i in ids if i != home_id][0]]
        print(f"  Marcador: {home_t['name']} {home_t['score']} - {away_t['score']} {away_t['name']}")
        if dry_run:
            print("  [DRY-RUN] no se escribe nada.")
            return True

        session.query(TeamGameStats).filter(TeamGameStats.game_id == game.id).delete()
        session.query(PlayerGameStats).filter(PlayerGameStats.game_id == game.id).delete()

        for tid, t in by_team.items():
            opp = by_team[[i for i in ids if i != tid][0]]
            row = {c: t["totals"][c] for c in _TEAM_COLS}
            row.update(four_factors(t["totals"], opp["totals"]))
            session.add(TeamGameStats(game_id=game.id, team_id=tid, is_home=(tid == home_id), **row))

            for p, pid in zip(t["players"], resolved[tid]):
                if p["_secs"] == 0 and not any(p[c] for c in ("pts", "reb", "ast", "stl", "blk", "tov", "pf")):
                    continue  # no jugo
                session.add(PlayerGameStats(
                    game_id=game.id, team_id=tid, player_id=pid, player_name=p["name"],
                    **{c: p[c] for c in _PLAYER_COLS},
                ))

        game.home_score = home_t["score"]
        game.away_score = away_t["score"]
        game.status = "final"

    print("  [OK] boxscore guardado.")
    return True


def collect_pdfs(args: list[str]) -> list[Path]:
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out += sorted(p.glob("*.pdf"))
        elif p.exists():
            out.append(p)
        else:
            import glob
            out += [Path(x) for x in sorted(glob.glob(a))]
    return out


def main():
    ap = argparse.ArgumentParser(description="Importa boxscores desde PDFs del Liveticker.")
    ap.add_argument("paths", nargs="+", help="PDFs, carpetas o patrones (*.pdf)")
    ap.add_argument("--dry-run", action="store_true", help="no escribe en la BD")
    ap.add_argument("--force", action="store_true", help="reemplaza stats ya existentes del partido")
    ap.add_argument("--game-id", type=int, default=None,
                    help="id del partido en la BD (fuerza el emparejamiento; solo con 1 PDF)")
    ap.add_argument("--create", action="store_true", help="crea el partido si no existe en la BD")
    args = ap.parse_args()

    pdfs = collect_pdfs(args.paths)
    if not pdfs:
        sys.exit("No he encontrado ningun PDF.")
    if args.game_id is not None and len(pdfs) != 1:
        sys.exit("--game-id solo se puede usar con un unico PDF.")

    ok = 0
    for pdf in pdfs:
        print(f"\n== {pdf.name}")
        try:
            parsed = parse_text(extract_text(pdf))
            print(f"  {parsed['teams'][0]['name']} vs {parsed['teams'][1]['name']} ({parsed['date']:%d.%m.%Y})")
            ok += bool(import_parsed(parsed, args.dry_run, args.force, args.create, args.game_id))
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(pdfs)} PDFs procesados correctamente.")


if __name__ == "__main__":
    main()
