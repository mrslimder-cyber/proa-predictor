import { notFound } from "next/navigation";
import {
  getSeasons,
  getStandings,
  getSeasonLeaders,
  MIN_GAMES_PLAYER,
  MIN_FT_ATT_PLAYER,
} from "@/lib/stats";
import SeasonSwitcher from "./season-switcher";
import { TeamInline, TeamLogo } from "@/lib/team-logo";

export const revalidate = 300;

function rankClass(i: number) {
  return i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : "";
}

export default async function SeasonPage({
  params,
}: {
  params: { season: string };
}) {
  const season = decodeURIComponent(params.season);
  const seasons = await getSeasons();
  if (!seasons.includes(season)) notFound();

  const [standings, leaders] = await Promise.all([
    getStandings(season),
    getSeasonLeaders(season),
  ]);

  const isPreseason = standings.length > 0 && standings.every((r) => r.played === 0);

  return (
    <div>
      <div className="breadcrumb">
        <a href="/temporadas">Temporadas</a>
        <span className="sep">/</span>
        <span className="current">{season}</span>
      </div>

      <div className="page-header">
        <div className="select-row">
          <SeasonSwitcher seasons={seasons} current={season} />
        </div>
        <h1 className="page-title">Temporada {season}</h1>
        <p className="page-sub">
          Clasificación real, líderes estadísticos y detalle por equipo.
        </p>
        {isPreseason && (
          <p className="page-sub" style={{ color: "var(--amber)", marginTop: 4 }}>
            Pretemporada: todavía no se ha jugado ningún partido, la tabla muestra
            los equipos inscritos con 0-0.
          </p>
        )}
      </div>

      {/* ---------- Clasificación ---------- */}
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Clasificación
        </div>
        {standings.length === 0 ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
            Todavía no hay partidos finalizados en esta temporada.
          </p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Equipo</th>
                  <th>PJ</th>
                  <th>V</th>
                  <th>D</th>
                  <th>PF</th>
                  <th>PC</th>
                  <th>+/-</th>
                </tr>
              </thead>
              <tbody>
                {standings.map((row, i) => (
                  <tr key={row.team.id}>
                    <td className="num">
                      <span className={`rank-badge ${rankClass(i)}`}>{i + 1}</span>
                    </td>
                    <td>
                      <TeamInline
                        teamId={row.team.id}
                        name={row.team.name}
                        size={22}
                        href={`/temporadas/${encodeURIComponent(season)}/equipos/${row.team.id}`}
                      />
                    </td>
                    <td className="num">{row.played}</td>
                    <td className="num">{row.wins}</td>
                    <td className="num">{row.losses}</td>
                    <td className="num">{row.pf}</td>
                    <td className="num">{row.pa}</td>
                    <td className="num">{row.diff > 0 ? `+${row.diff}` : row.diff}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ---------- Selector de equipo ---------- */}
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Ver un equipo
        </div>
        {standings.length === 0 ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
            No hay equipos con partidos jugados todavía.
          </p>
        ) : (
          <div className="card-grid">
            {standings.map((row) => (
              <a
                key={row.team.id}
                href={`/temporadas/${encodeURIComponent(season)}/equipos/${row.team.id}`}
                className="tile team-tile"
              >
                <TeamLogo teamId={row.team.id} name={row.team.name} size={34} />
                <div>
                  <div className="tile-title" style={{ fontSize: 14 }}>
                    {row.team.name}
                  </div>
                  <div className="tile-sub">
                    {row.wins}V - {row.losses}D
                  </div>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>

      {/* ---------- Líderes ---------- */}
      <div className="section-title" style={{ marginTop: 26, marginBottom: 12 }}>
        <span className="dot" /> Líderes de la temporada
      </div>

      <div className="leader-grid">
        <LeaderPanel
          title="Puntos por partido · Equipos"
          empty="Sin datos suficientes todavía."
          items={leaders.teamPoints.map((t, i) => ({
            key: t.team.id,
            rank: i,
            primary: t.team.name,
            teamId: t.team.id,
            secondary: `${t.games} partidos`,
            value: t.avg.toFixed(1),
            unit: "pts",
          }))}
        />
        <LeaderPanel
          title={`Puntos por partido · Jugadores (mín. ${MIN_GAMES_PLAYER} PJ)`}
          empty="Ningún jugador cumple el mínimo de partidos todavía."
          items={leaders.playerPoints.map((p, i) => ({
            key: p.playerId,
            rank: i,
            primary: p.playerName,
            teamId: p.team?.id,
            secondary: `${p.team?.name ?? "—"} · ${p.games} PJ`,
            value: p.avg.toFixed(1),
            unit: "pts",
          }))}
        />
        <LeaderPanel
          title="% Tiros libres · Equipos"
          empty="Sin datos suficientes todavía."
          items={leaders.teamFtPct.map((t, i) => ({
            key: t.team.id,
            rank: i,
            primary: t.team.name,
            teamId: t.team.id,
            secondary: `${t.games} partidos`,
            value: (t.pct * 100).toFixed(1),
            unit: "%",
          }))}
        />
        <LeaderPanel
          title={`% Tiros libres · Jugadores (mín. ${MIN_GAMES_PLAYER} PJ, ${MIN_FT_ATT_PLAYER} TL)`}
          empty="Ningún jugador cumple los mínimos todavía."
          items={leaders.playerFtPct.map((p, i) => ({
            key: p.playerId,
            rank: i,
            primary: p.playerName,
            teamId: p.team?.id,
            secondary: `${p.team?.name ?? "—"} · ${p.games} PJ`,
            value: p.pct != null ? (p.pct * 100).toFixed(1) : "—",
            unit: "%",
          }))}
        />
      </div>
    </div>
  );
}

function LeaderPanel({
  title,
  items,
  empty,
}: {
  title: string;
  empty: string;
  items: {
    key: number;
    rank: number;
    primary: string;
    teamId?: number;
    secondary: string;
    value: string;
    unit: string;
  }[];
}) {
  return (
    <div className="panel">
      <div className="section-title">{title}</div>
      {items.length === 0 ? (
        <p style={{ color: "var(--chalk-dim)", fontSize: 13.5 }}>{empty}</p>
      ) : (
        <ul className="leader-list">
          {items.map((it) => (
            <li key={it.key} className="leader-row">
              <span className={`rank-badge ${rankClass(it.rank)}`}>{it.rank + 1}</span>
              {it.teamId != null && (
                <TeamLogo teamId={it.teamId} name={it.primary} size={26} />
              )}
              <div className="leader-name">
                <div className="primary">{it.primary}</div>
                <div className="secondary">{it.secondary}</div>
              </div>
              <div className="leader-value">
                {it.value}
                <span className="unit">{it.unit}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
