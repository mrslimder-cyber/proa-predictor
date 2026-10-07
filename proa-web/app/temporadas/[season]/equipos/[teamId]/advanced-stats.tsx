"use client";

import { useState } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, LabelList, ReferenceLine } from "recharts";
import type { Team } from "@/lib/supabase";
import type { TeamAdvancedRow, TeamFourFactorsRow } from "@/lib/stats";

const GOLD = "#FFCE00";
const RED = "#DD0000";
const DIM = "#a1a1ab";
const GRAY = "#34343c";
const PANEL = "#18181d";
const LINE = "#2a2a31";

type Metric<T> = {
  key: keyof T;
  title: string;
  tab: string; // etiqueta corta de la pestaña
  hint: string;
  higherIsBetter?: boolean; // por defecto true
  decimals?: number;
  pct?: boolean; // el valor viene en fracción 0-1
};

const ADVANCED: Metric<TeamAdvancedRow>[] = [
  { key: "offRating", title: "Rating ofensivo", tab: "Ofensivo", hint: "Puntos por 100 posesiones · más es mejor" },
  { key: "defRating", title: "Rating defensivo", tab: "Defensivo", hint: "Puntos recibidos por 100 posesiones · menos es mejor", higherIsBetter: false },
  { key: "possessionsPerGame", title: "Posesiones por partido", tab: "Posesiones", hint: "Ritmo de juego" },
  { key: "pointsPerPossession", title: "Puntos por posesión", tab: "Pts / posesión", hint: "Eficiencia ofensiva", decimals: 2 },
];

const FOUR_FACTORS: Metric<TeamFourFactorsRow>[] = [
  { key: "efgPct", title: "eFG%", tab: "eFG%", hint: "Efectividad de tiro · más es mejor", pct: true },
  { key: "tovPct", title: "% de pérdidas", tab: "Pérdidas", hint: "Menos es mejor", pct: true, higherIsBetter: false },
  { key: "orbPct", title: "% rebote ofensivo", tab: "Reb. ofensivo", hint: "Más es mejor", pct: true },
  { key: "ftRate", title: "Ratio de tiros libres", tab: "Tiros libres", hint: "Libres anotados / tiros de campo intentados", pct: true },
];

function RankChart<T extends { team: Team }>({ rows, teamId, m }: { rows: T[]; teamId: number; m: Metric<T> }) {
  const val = (r: T) => (r[m.key] as unknown as number) * (m.pct ? 100 : 1);
  const d = m.decimals ?? 1;
  const fmt = (v: number) => v.toFixed(d) + (m.pct ? "%" : "");
  const higher = m.higherIsBetter !== false;

  const sorted = [...rows].sort((a, b) => (higher ? val(b) - val(a) : val(a) - val(b)));
  const own = sorted.find((r) => r.team.id === teamId);
  if (!own) return null;

  const values = sorted.map(val);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const avg = values.reduce((a, v) => a + v, 0) / values.length;
  const data = sorted.map((r) => ({
    name: r.team.name.length > 14 ? r.team.name.slice(0, 14) + "…" : r.team.name,
    value: val(r),
    isTeam: r.team.id === teamId,
  }));

  return (
    <div key={String(m.key)}>
      <div className="rank-head">
        <div>
          <div className="rank-title">{m.title}</div>
          <div className="rank-hint">{m.hint}</div>
        </div>
        <div className="rank-chip"><strong>#{sorted.indexOf(own) + 1}</strong> de {rows.length}</div>
      </div>
      <div className="rank-value">{fmt(val(own))}</div>
      <div style={{ width: "100%", height: data.length * 26 + 24 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 14, right: 44, left: 0, bottom: 0 }} barCategoryGap={4}>
            <XAxis type="number" hide domain={[lo - span * 0.45, hi + span * 0.05]} />
            <YAxis type="category" dataKey="name" width={104} tick={{ fill: DIM, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{ background: PANEL, border: `1px solid ${LINE}`, borderRadius: 12, fontSize: 12.5 }}
              labelStyle={{ color: DIM }}
              formatter={(v: any) => [fmt(Number(v)), m.title]}
            />
            <ReferenceLine x={avg} stroke={RED} strokeDasharray="4 3" label={{ value: "media", position: "top", fill: DIM, fontSize: 10 }} />
            <Bar dataKey="value" radius={[0, 8, 8, 0]}>
              {data.map((x, i) => (
                <Cell key={i} fill={x.isTeam ? GOLD : GRAY} />
              ))}
              <LabelList dataKey="value" position="right" formatter={(v: any) => fmt(Number(v))} fill={DIM} fontSize={11} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function RankPanel<T extends { team: Team }>({ title, rows, teamId, metrics }: { title: string; rows: T[]; teamId: number; metrics: Metric<T>[] }) {
  const [idx, setIdx] = useState(0);
  if (!rows.some((r) => r.team.id === teamId)) return null;
  const m = metrics[idx];
  return (
    <div className="panel">
      <div className="section-title"><span className="dot" /> {title}</div>
      <div className="rank-tabs" role="tablist">
        {metrics.map((x, i) => (
          <button
            key={String(x.key)}
            type="button"
            role="tab"
            aria-selected={i === idx}
            className={`rank-tab ${i === idx ? "active" : ""}`}
            onClick={() => setIdx(i)}
          >
            {x.tab}
          </button>
        ))}
      </div>
      <RankChart rows={rows} teamId={teamId} m={m} />
    </div>
  );
}

export function AdvancedStatsPanel({ rows, teamId }: { rows: TeamAdvancedRow[]; teamId: number }) {
  return <RankPanel title="Ranking de la liga · ataque, defensa y ritmo" rows={rows} teamId={teamId} metrics={ADVANCED} />;
}

export function FourFactorsPanel({ rows, teamId }: { rows: TeamFourFactorsRow[]; teamId: number }) {
  return <RankPanel title="Four Factors (Dean Oliver) · ranking de la liga" rows={rows} teamId={teamId} metrics={FOUR_FACTORS} />;
}
