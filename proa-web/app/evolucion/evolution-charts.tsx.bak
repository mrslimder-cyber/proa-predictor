"use client";

import {
  ResponsiveContainer, ComposedChart, Bar, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import type { EvolutionJornada } from "@/lib/stats";

const AMBER = "#ff8a2b";
const DIM = "#98a3ad";
const LINE = "#29323d";
const PANEL = "#1a2028";
const WIN = "#46cf8b";

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div style={{ background: PANEL, border: `1px solid ${LINE}`, borderRadius: 8, padding: "8px 12px", fontSize: 12.5, color: "#f3f5f6" }}>
      <div style={{ color: DIM, marginBottom: 4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <strong>{typeof p.value === "number" ? p.value.toFixed(1) : p.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function EvolutionCharts({ jornadas }: { jornadas: EvolutionJornada[] }) {
  const accData = jornadas.map((j) => ({ jornada: j.label, "Acierto ganador": Math.round(j.accuracy * 100) }));
  const marginData = jornadas.map((j) => ({
    jornada: j.label,
    "Margen predicho": Number(j.avgPredictedMargin.toFixed(1)),
    "Margen real": Number(j.avgActualMargin.toFixed(1)),
    "Error medio": Number(j.avgMarginError.toFixed(1)),
  }));

  const totalGames = jornadas.reduce((a, j) => a + j.games, 0);
  const overallAcc = jornadas.reduce((a, j) => a + j.accuracy * j.games, 0) / totalGames;
  const overallMae = jornadas.reduce((a, j) => a + j.avgMarginError * j.games, 0) / totalGames;

  return (
    <>
      <div className="pill-row" style={{ marginBottom: 16 }}>
        <div className="stat-pill">
          <div className="label">Acierto ganador (global)</div>
          <div className="value">{(overallAcc * 100).toFixed(1)}%</div>
        </div>
        <div className="stat-pill">
          <div className="label">Error medio de margen</div>
          <div className="value">{overallMae.toFixed(1)} pts</div>
        </div>
        <div className="stat-pill">
          <div className="label">Jornadas analizadas</div>
          <div className="value">{jornadas.length}</div>
        </div>
      </div>

      <div className="panel chart-card">
        <div className="section-title"><span className="dot" /> % de acierto en el ganador, por jornada</div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={accData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="jornada" tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="Acierto ganador" fill={WIN} radius={[4, 4, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel chart-card">
        <div className="section-title"><span className="dot" /> Margen predicho vs. margen real, por jornada</div>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={marginData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="jornada" tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
              <YAxis tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12, color: DIM }} />
              <Line type="monotone" dataKey="Margen predicho" stroke={AMBER} strokeWidth={2.5} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="Margen real" stroke={DIM} strokeWidth={2} dot={{ r: 3 }} strokeDasharray="4 3" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel chart-card">
        <div className="section-title"><span className="dot" /> Error medio del margen (puntos), por jornada</div>
        <div className="chart-wrap short">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={marginData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid stroke={LINE} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="jornada" tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
              <YAxis tick={{ fill: DIM, fontSize: 11 }} axisLine={{ stroke: LINE }} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="Error medio" fill={AMBER} radius={[4, 4, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </>
  );
}