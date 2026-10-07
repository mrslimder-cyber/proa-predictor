"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { TeamGameLog, RosterRow } from "@/lib/stats";

const AMBER = "#ff8a2b";
const DIM = "#98a3ad";
const LINE = "#29323d";
const PANEL = "#1a2028";

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      style={{
        background: PANEL,
        border: `1px solid ${LINE}`,
        borderRadius: 8,
        padding: "8px 12px",
        fontSize: 12.5,
        color: "#f3f5f6",
      }}
    >
      <div style={{ color: DIM, marginBottom: 4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <strong>{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function PointsTrendChart({ gameLog }: { gameLog: TeamGameLog[] }) {
  const data = gameLog.map((g, i) => ({
    jornada: g.matchday ?? i + 1,
    Anotados: g.pts,
    Recibidos: g.oppPts,
    rival: g.opponent,
  }));

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="jornada"
            tick={{ fill: DIM, fontSize: 11 }}
            axisLine={{ stroke: LINE }}
            tickLine={false}
          />
          <YAxis tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
          <Tooltip content={<ChartTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12, color: DIM }} />
          <Line type="monotone" dataKey="Anotados" stroke={AMBER} strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="Recibidos" stroke={DIM} strokeWidth={2} dot={false} strokeDasharray="4 3" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function TopScorersChart({ roster }: { roster: RosterRow[] }) {
  const data = [...roster]
    .sort((a, b) => b.ptsAvg - a.ptsAvg)
    .slice(0, 6)
    .map((r) => ({ name: r.playerName.split(" ").slice(-1)[0], Puntos: Number(r.ptsAvg.toFixed(1)) }));

  return (
    <div className="chart-wrap short">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
          <YAxis tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <Bar dataKey="Puntos" fill={AMBER} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
