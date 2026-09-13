import { notFound } from "next/navigation";
import { PointsTrendChart, TopScorersChart } from "./team-charts";
import TeamSwitcher from "./team-switcher";
import { TeamLogo } from "@/lib/team-logo";
import type { RosterRow } from "@/lib/stats";
import { AdvancedStatsPanel } from "./advanced-stats";
import { getTeamDetail, getSeasonTeams, getSeasonAdvancedStats, MIN_GAMES_PLAYER, MIN_FT_ATT_PLAYER } from "@/lib/stats";


export const revalidate = 300;

export default async function TeamDetailPage({
  params,
}: {
  params: { season: string; teamId: string };
}) {
  const season = decodeURIComponent(params.season);
  const teamId = Number(params.teamId);
  if (Number.isNaN(teamId)) notFound();

  const [detail, seasonTeams] = await Promise.all([
    getTeamDetail(season, teamId),
    getSeasonTeams(season),
    getSeasonAdvancedStats(season),
  ]);

  if (!detail) notFound();

  const { team, standing, roster, topPoints, topRebounds, topAssists, topFt, gameLog, seasonAvg } = detail;

  return (
    <div>
      <div className="breadcrumb">
        <a href="/temporadas">Temporadas</a>
        <span className="sep">/</span>
        <a href={`/temporadas/${encodeURIComponent(season)}`}>{season}</a>
        <span className="sep">/</span>
        <span className="current">{team.name}</span>
      </div>

      <div className="select-row">
        <TeamSwitcher season={season} teams={seasonTeams} current={teamId} />
      </div>

      <div className="team-header">
        <TeamLogo teamId={team.id} name={team.name} size={52} />
        <div>
          <h1>{team.name}</h1>
          <div className="team-header-sub">
            Temporada {season}
            {standing && (
              <>
                {" · "}
                {standing.wins}V - {standing.losses}D
                {" · "}
                {standing.played} partidos
              </>
            )}
          </div>
        </div>
      </div>

      {/* ---------- Medias de equipo ---------- */}
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Medias de la temporada
        </div>
        <div className="pill-row">
          <div className="stat-pill">
            <div className="label">Puntos</div>
            <div className="value">{seasonAvg.pts.toFixed(1)}</div>
          </div>
          <div className="stat-pill">
            <div className="label">Rebotes</div>
            <div className="value">{seasonAvg.reb.toFixed(1)}</div>
          </div>
          <div className="stat-pill">
            <div className="label">Asistencias</div>
            <div className="value">{seasonAvg.ast.toFixed(1)}</div>
          </div>
          <div className="stat-pill">
            <div className="label">% Tiros libres</div>
            <div className="value">
              {seasonAvg.ftPct != null ? `${(seasonAvg.ftPct * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          {standing && (
            <div className="stat-pill">
              <div className="label">Diferencial</div>
              <div className="value">{standing.diff > 0 ? `+${standing.diff}` : standing.diff}</div>
            </div>
          )}
        </div>
      </div>

      {/* ---------- Últimos resultados ---------- */}
      {gameLog.length > 0 && (
        <div className="panel">
          <div className="section-title">
            <span className="dot" /> Últimos resultados
          </div>
          <div className="form-row">
            {gameLog.slice(-10).map((g) => (
              <a
                key={g.gameId}
                href={`/partidos/${g.gameId}`}
                className={`form-bubble ${g.win ? "win" : "loss"}`}
                title={`${g.isHome ? "vs" : "@"} ${g.opponent}: ${g.pts}-${g.oppPts}`}
              >
                {g.win ? "W" : "L"}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* ---------- Gráficos ---------- */}
      {gameLog.length > 0 && (
        <div className="panel chart-card">
          <div className="section-title">
            <span className="dot" /> Puntos anotados vs. recibidos por jornada
          </div>
          <PointsTrendChart gameLog={gameLog} />
        </div>
      )}

      {roster.length > 0 && (
        <div className="panel chart-card">
          <div className="section-title">
            <span className="dot" /> Media de puntos por jugador
          </div>
          <TopScorersChart roster={roster} />
        </div>
      )}

      <AdvancedStatsPanel rows={advancedStats} teamId={teamId} />

      {/* ---------- Top 3 por categoría ---------- */}
      <div className="section-title" style={{ marginTop: 26, marginBottom: 12 }}>
        <span className="dot" /> Top 3 del equipo (mín. {MIN_GAMES_PLAYER} PJ)
      </div>
      <div className="stat-card-grid">
        <PodiumCard title="Puntos por partido" rows={topPoints} statKey="ptsAvg" suffix="" />
        <PodiumCard title="Rebotes por partido" rows={topRebounds} statKey="rebAvg" suffix="" />
        <PodiumCard title="Asistencias por partido" rows={topAssists} statKey="astAvg" suffix="" />
        <PodiumCard
          title={`% Tiros libres (mín. ${MIN_FT_ATT_PLAYER} TL)`}
          rows={topFt}
          statKey="ftPct"
          suffix="%"
          isPct
        />
      </div>

      {/* ---------- Plantilla ---------- */}
      <div className="panel" style={{ marginTop: 26 }}>
        <div className="section-title">
          <span className="dot" /> Plantilla ({roster.length} jugadores)
        </div>
        {roster.length === 0 ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
            Todavía no hay estadísticas de jugadores para este equipo en esta temporada.
          </p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Jugador</th>
                  <th>PJ</th>
                  <th>Pts</th>
                  <th>Reb</th>
                  <th>Ast</th>
                  <th>% TL</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((p) => (
                  <tr key={p.playerId}>
                    <td>{p.playerName}</td>
                    <td className="num">{p.games}</td>
                    <td className="num">{p.ptsAvg.toFixed(1)}</td>
                    <td className="num">{p.rebAvg.toFixed(1)}</td>
                    <td className="num">{p.astAvg.toFixed(1)}</td>
                    <td className="num">{p.ftPct != null ? `${(p.ftPct * 100).toFixed(0)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function PodiumCard({
  title,
  rows,
  statKey,
  suffix,
  isPct,
}: {
  title: string;
  rows: RosterRow[];
  statKey: keyof RosterRow;
  suffix: string;
  isPct?: boolean;
}) {
  const max = Math.max(1, ...rows.map((r) => Number(r[statKey] ?? 0)));
  return (
    <div className="panel">
      <div className="section-title">{title}</div>
      {rows.length === 0 ? (
        <p style={{ color: "var(--chalk-dim)", fontSize: 13.5 }}>Sin datos suficientes todavía.</p>
      ) : (
        <div className="podium">
          {rows.map((r, i) => {
            const raw = Number(r[statKey] ?? 0);
            const display = isPct ? (raw * 100).toFixed(1) : raw.toFixed(1);
            const pct = Math.max(4, (raw / max) * 100);
            return (
              <div className="podium-row" key={r.playerId}>
                <span className={`rank-badge ${i === 0 ? "top1" : i === 1 ? "top2" : "top3"}`}>{i + 1}</span>
                <span className="podium-name">{r.playerName}</span>
                <span className="podium-bar-track">
                  <span className="podium-bar-fill" style={{ width: `${pct}%` }} />
                </span>
                <span className="podium-value">
                  {display}
                  {suffix}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
