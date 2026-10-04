import type { MatchupExtras, TeamScorer } from "@/lib/stats";

type Line = {
  label: string;
  h: number | null;
  a: number | null;
  hRank: string | null;
  aRank: string | null;
  fmt: (v: number) => string;
  lowerBetter: boolean;
};

function line<T extends { team: { id: number } }>(
  label: string,
  rows: T[],
  homeId: number,
  awayId: number,
  get: (r: T) => number,
  fmt: (v: number) => string,
  lowerBetter = false
): Line {
  const sorted = [...rows].sort((x, y) => (lowerBetter ? get(x) - get(y) : get(y) - get(x)));
  const rankOf = (id: number) => {
    const i = sorted.findIndex((r) => r.team.id === id);
    return i < 0 ? null : `#${i + 1} de ${rows.length}`;
  };
  const h = rows.find((r) => r.team.id === homeId);
  const a = rows.find((r) => r.team.id === awayId);
  return {
    label,
    h: h ? get(h) : null,
    a: a ? get(a) : null,
    hRank: rankOf(homeId),
    aRank: rankOf(awayId),
    fmt,
    lowerBetter,
  };
}

function winner(l: Line): "home" | "away" | null {
  if (l.h == null || l.a == null || l.h === l.a) return null;
  const homeBetter = l.lowerBetter ? l.h < l.a : l.h > l.a;
  return homeBetter ? "home" : "away";
}

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const dec1 = (v: number) => v.toFixed(1);

export function MatchupExtrasPanel({
  extras,
  homeId,
  awayId,
  homeName,
  awayName,
}: {
  extras: MatchupExtras;
  homeId: number;
  awayId: number;
  homeName: string;
  awayName: string;
}) {
  const { advanced, fourFactors, scorers } = extras;

  const lines: Line[] = [
    line("Rating ofensivo", advanced, homeId, awayId, (r) => r.offRating, dec1),
    line("Rating defensivo", advanced, homeId, awayId, (r) => r.defRating, dec1, true),
    line("Rating neto", advanced, homeId, awayId, (r) => r.netRating, dec1),
    line("Ritmo (posesiones)", advanced, homeId, awayId, (r) => r.possessionsPerGame, dec1),
    line("eFG%", fourFactors, homeId, awayId, (r) => r.efgPct, pct),
    line("% Pérdidas", fourFactors, homeId, awayId, (r) => r.tovPct, pct, true),
    line("% Rebote ofensivo", fourFactors, homeId, awayId, (r) => r.orbPct, pct),
    line("Ratio tiros libres", fourFactors, homeId, awayId, (r) => r.ftRate, pct),
  ];

  const hasData = lines.some((l) => l.h != null || l.a != null);
  const hasScorers = scorers.home.length > 0 || scorers.away.length > 0;
  if (!hasData && !hasScorers) return null;

  return (
    <>
      {hasData && (
        <div className="panel">
          <div className="section-title">
            <span className="dot" /> Ratings y Four Factors (temporada)
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th className="num">{homeName}</th>
                  <th style={{ textAlign: "center" }}>Estadística</th>
                  <th className="num">{awayName}</th>
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => {
                  const w = winner(l);
                  return (
                    <tr key={l.label}>
                      <td className={`num ${w === "home" ? "stat-win" : ""}`}>
                        {l.h != null ? l.fmt(l.h) : "—"}
                        {l.hRank && <div style={{ fontSize: 10.5, color: "var(--chalk-dim)" }}>{l.hRank}</div>}
                      </td>
                      <td style={{ textAlign: "center", color: "var(--chalk-dim)", fontSize: 13 }}>
                        {l.label}
                      </td>
                      <td className={`num ${w === "away" ? "stat-win" : ""}`}>
                        {l.a != null ? l.fmt(l.a) : "—"}
                        {l.aRank && <div style={{ fontSize: 10.5, color: "var(--chalk-dim)" }}>{l.aRank}</div>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {hasScorers && (
        <div className="summary-grid">
          <ScorersCard title={`Líderes de puntos · ${homeName}`} players={scorers.home} />
          <ScorersCard title={`Líderes de puntos · ${awayName}`} players={scorers.away} />
        </div>
      )}
    </>
  );
}

function ScorersCard({ title, players }: { title: string; players: TeamScorer[] }) {
  return (
    <div className="panel">
      <div className="section-title">
        <span className="dot" /> {title}
      </div>
      {players.length === 0 ? (
        <p style={{ color: "var(--chalk-dim)", fontSize: 13.5 }}>Sin datos todavía.</p>
      ) : (
        <ul className="leader-list">
          {players.map((p, i) => (
            <li key={p.playerId} className="leader-row">
              <span className={`rank-badge ${i === 0 ? "top1" : i === 1 ? "top2" : "top3"}`}>{i + 1}</span>
              <div className="leader-name">
                <div className="primary">{p.playerName}</div>
                <div className="secondary">{p.games} PJ</div>
              </div>
              <div className="leader-value">
                {p.ptsAvg.toFixed(1)}
                <span className="unit">pts</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}