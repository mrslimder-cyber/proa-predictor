"use client";

import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from "recharts";
import type { TeamAdvancedRow, TeamFourFactorsRow } from "@/lib/stats";

export function FourFactorsPanel({ rows, teamId }: { rows: TeamFourFactorsRow[]; teamId: number }) {
  const own = rows.find((r) => r.team.id === teamId);
  if (!own) return null;
  const total = rows.length;

  const rankOf = (key: keyof TeamFourFactorsRow, higherIsBetter = true) => {
    const sorted = [...rows].sort((a, b) =>
      higherIsBetter ? (b[key] as number) - (a[key] as number) : (a[key] as number) - (b[key] as number)
    );
    return sorted.findIndex((r) => r.team.id === teamId) + 1;
  };
  const leagueAvg = (key: keyof TeamFourFactorsRow) =>
    rows.reduce((a, r) => a + (r[key] as number), 0) / rows.length;

  const pill = (label: string, key: keyof TeamFourFactorsRow, higherIsBetter = true) => (
    <div className="stat-pill" key={key}>
      <div className="label">{label}</div>
      <div className="value">{((own[key] as number) * 100).toFixed(1)}%</div>
      <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>
        #{rankOf(key, higherIsBetter)} de {total} · liga {((leagueAvg(key)) * 100).toFixed(1)}%
      </div>
    </div>
  );

  return (
    <div className="panel">
      <div className="section-title"><span className="dot" /> Four Factors (Dean Oliver)</div>
      <div className="pill-row">
        {pill("eFG%", "efgPct")}
        {pill("% Pérdidas (TOV%)", "tovPct", false)}
        {pill("% Rebote ofensivo", "orbPct")}
        {pill("Ratio tiros libres", "ftRate")}
      </div>
    </div>
  );
}
const AMBER = "#ff8a2b";
const DIM = "#98a3ad";
const LINE = "#29323d";
const PANEL = "#1a2028";
const GRAY = "#3a4552";

function RankChart({
  rows, statKey, highlightTeamId, higherIsBetter = true,
}: {
  rows: TeamAdvancedRow[];
  statKey: keyof TeamAdvancedRow;
  highlightTeamId: number;
  higherIsBetter?: boolean;
}) {
  const sorted = [...rows].sort((a, b) =>
    higherIsBetter ? (b[statKey] as number) - (a[statKey] as number) : (a[statKey] as number) - (b[statKey] as number)
  );
  const data = sorted.map((r) => ({
    name: r.team.name.length > 12 ? r.team.name.slice(0, 12) + "…" : r.team.name,
    value: Number((r[statKey] as number).toFixed(1)),
    isTeam: r.team.id === highlightTeamId,
  }));

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 20, left: 8, bottom: 0 }}>
          <CartesianGrid stroke={LINE} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
          <YAxis type="category" dataKey="name" width={100} tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
          <Tooltip contentStyle={{ background: PANEL, border: `1px solid ${LINE}`, borderRadius: 8, fontSize: 12.5 }} labelStyle={{ color: DIM }} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.isTeam ? AMBER : GRAY} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function AdvancedStatsPanel({ rows, teamId }: { rows: TeamAdvancedRow[]; teamId: number }) {
  const own = rows.find((r) => r.team.id === teamId);
  if (!own) return null;

  const total = rows.length;
  const rankOf = (statKey: keyof TeamAdvancedRow, higherIsBetter = true) => {
    const sorted = [...rows].sort((a, b) =>
      higherIsBetter ? (b[statKey] as number) - (a[statKey] as number) : (a[statKey] as number) - (b[statKey] as number)
    );
    return sorted.findIndex((r) => r.team.id === teamId) + 1;
  };
  const leagueAvg = (statKey: keyof TeamAdvancedRow) =>
    rows.reduce((a, r) => a + (r[statKey] as number), 0) / rows.length;

  return (
    <>
      <div className="panel">
        <div className="section-title"><span className="dot" /> Estadísticas avanzadas vs. la liga</div>
        <div className="pill-row">
          <div className="stat-pill">
            <div className="label">Puntos por posesión</div>
            <div className="value">{own.pointsPerPossession.toFixed(2)}</div>
            <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>
              #{rankOf("pointsPerPossession")} de {total} · liga {leagueAvg("pointsPerPossession").toFixed(2)}
            </div>
          </div>
          <div className="stat-pill">
            <div className="label">Rating ofensivo</div>
            <div className="value">{own.offRating.toFixed(1)}</div>
            <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>
              #{rankOf("offRating")} de {total} · liga {leagueAvg("offRating").toFixed(1)}
            </div>
          </div>
          <div className="stat-pill">
            <div className="label">Rating defensivo</div>
            <div className="value">{own.defRating.toFixed(1)}</div>
            <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>
              #{rankOf("defRating", false)} de {total} · liga {leagueAvg("defRating").toFixed(1)}
            </div>
          </div>
          <div className="stat-pill">
            <div className="label">Ritmo (posesiones/partido)</div>
            <div className="value">{own.possessionsPerGame.toFixed(1)}</div>
            <div style={{ fontSize: 11, color: "var(--chalk-dim)", marginTop: 2 }}>
              #{rankOf("possessionsPerGame")} de {total} · liga {leagueAvg("possessionsPerGame").toFixed(1)}
            </div>
          </div>
        </div>
      </div>

      <div className="panel chart-card">
        <div className="section-title"><span className="dot" /> Rating ofensivo — ranking de la liga</div>
        <RankChart rows={rows} statKey="offRating" highlightTeamId={teamId} higherIsBetter />
      </div>

      <div className="panel chart-card">
        <div className="section-title"><span className="dot" /> Rating defensivo — ranking de la liga (menos es mejor)</div>
        <RankChart rows={rows} statKey="defRating" highlightTeamId={teamId} higherIsBetter={false} />
      </div>
    </>
  );
}