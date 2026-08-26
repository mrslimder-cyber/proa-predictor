"use client";

import { useState } from "react";
import type { TeamGameStats, GameInsightRow } from "@/lib/supabase";

// Para estas stats, un valor MÁS BAJO es mejor (todas las demás: más alto = mejor).
const LOWER_IS_BETTER = new Set<keyof TeamGameStats>(["tov", "pf"]);

type RowDef = { key: keyof TeamGameStats; label: string; pct?: boolean };

const ROWS: RowDef[] = [
  { key: "pts", label: "Puntos" },
  { key: "fg2_made", label: "Tiros de 2 anotados" },
  { key: "fg2_att", label: "Tiros de 2 intentados" },
  { key: "fg3_made", label: "Tiros de 3 anotados" },
  { key: "fg3_att", label: "Tiros de 3 intentados" },
  { key: "ft_made", label: "Tiros libres anotados" },
  { key: "ft_att", label: "Tiros libres intentados" },
  { key: "oreb", label: "Rebotes ofensivos" },
  { key: "dreb", label: "Rebotes defensivos" },
  { key: "reb", label: "Rebotes totales" },
  { key: "ast", label: "Asistencias" },
  { key: "tov", label: "Pérdidas" },
  { key: "stl", label: "Robos" },
  { key: "blk", label: "Tapones" },
  { key: "pf", label: "Faltas" },
  { key: "efg_pct", label: "eFG%", pct: true },
  { key: "tov_pct", label: "% Pérdidas", pct: true },
  { key: "orb_pct", label: "% Rebote ofensivo", pct: true },
  { key: "ft_rate", label: "Ratio tiros libres", pct: true },
];

function winningSide(
  homeVal: number | null,
  awayVal: number | null,
  key: keyof TeamGameStats
): "home" | "away" | null {
  if (homeVal == null || awayVal == null || homeVal === awayVal) return null;
  const lowerBetter = LOWER_IS_BETTER.has(key);
  const homeWins = lowerBetter ? homeVal < awayVal : homeVal > awayVal;
  return homeWins ? "home" : "away";
}

function fmt(val: number | null | undefined, pct?: boolean) {
  if (val == null) return "—";
  return pct ? `${(val * 100).toFixed(1)}%` : String(val);
}

export function BoxscorePanel({
  homeStats,
  awayStats,
  homeName,
  awayName,
  insight,
}: {
  homeStats: TeamGameStats | null;
  awayStats: TeamGameStats | null;
  homeName: string;
  awayName: string;
  insight: GameInsightRow | null;
}) {
  const [showSummary, setShowSummary] = useState(false);

  if (!homeStats || !awayStats) {
    return (
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Estadísticas del partido
        </div>
        <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
          Todavía no hay boxscore detallado guardado para este partido.
        </p>
      </div>
    );
  }

  const winnerSide = insight?.key_factors?.[0]?.favors;
  const winnerName = winnerSide === "away" ? awayName : homeName;

  return (
    <div className="panel">
      <div className="section-title">
        <span className="dot" /> Estadísticas del partido
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
            {ROWS.map((r) => {
              const h = (homeStats as any)[r.key] as number | null;
              const a = (awayStats as any)[r.key] as number | null;
              const winner = winningSide(h, a, r.key);
              return (
                <tr key={String(r.key)}>
                  <td className={`num ${winner === "home" ? "stat-win" : ""}`}>{fmt(h, r.pct)}</td>
                  <td style={{ textAlign: "center", color: "var(--chalk-dim)", fontSize: 13 }}>
                    {r.label}
                  </td>
                  <td className={`num ${winner === "away" ? "stat-win" : ""}`}>{fmt(a, r.pct)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 18 }}>
        {!insight ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 13 }}>
            Resumen todavía no generado para este partido (se genera junto al resto
            del pipeline: <code>python -m models.game_insights</code>).
          </p>
        ) : !showSummary ? (
          <button
            className="season-select"
            style={{ cursor: "pointer" }}
            onClick={() => setShowSummary(true)}
          >
            Generar resumen
          </button>
        ) : (
          <div className="stat-pill" style={{ maxWidth: "none", minWidth: 0 }}>
            <div className="label">Por qué ganó {winnerName}</div>
            <p style={{ margin: "8px 0 0", fontSize: 14, lineHeight: 1.5, fontWeight: 400 }}>
              {insight.summary_text}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
