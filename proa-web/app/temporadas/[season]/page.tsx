import { notFound } from "next/navigation";
import {
  getSeasons,
  getStandings,
  getSeasonLeaders,
  getSeasonUpcomingJornada,
  getLastJornadaGames,
  getSeasonJornadas,
  MIN_GAMES_PLAYER,
  MIN_FT_ATT_PLAYER,
} from "@/lib/stats";
import SeasonSwitcher from "./season-switcher";
import { TeamInline, TeamLogo } from "@/lib/team-logo";

export const revalidate = 300;

function rankClass(i: number) {
  return i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : "";
}

function fmtDate(d: string) {
  return new Date(d).toLocaleDateString("es-ES", { weekday: "short", day: "2-digit", month: "short" });
}

export default async function SeasonPage({
  params,
}: {
  params: { season: string };
}) {
  const season = decodeURIComponent(params.season);
  const seasons = await getSeasons();
  if (!seasons.includes(season)) notFound();

  const [standings, leaders, upcoming, lastJornada, jornadas] = await Promise.all([
    getStandings(season),
    getSeasonLeaders(season),
    getSeasonUpcomingJornada(season),
    getLastJornadaGames(season),
    getSeasonJornadas(season),
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

      {/* ---------- Próxima jornada ---------- */}
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Próxima jornada
        </div>
        {upcoming.length === 0 ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
            No hay partidos programados todavía para esta temporada.
          </p>
        ) : (
          upcoming.map((g) => (
            <a className="panel game-link" key={g.gameId} href={`/partidos/${g.gameId}`}>
              <div className="meta-row">
                <span>{fmtDate(g.date)}</span>
              </div>
              <div className="matchup">
                <div className="matchup-team">
                  {g.home && <TeamLogo teamId={g.home.id} name={g.home.name} size={26} />}
                  <div className="team-name">{g.home?.name ?? "Equipo local"}</div>
                </div>
                <div className="vs">vs</div>
                <div className="matchup-team away">
                  {g.away && <TeamLogo teamId={g.away.id} name={g.away.name} size={26} />}
                  <div className="team-name away">{g.away?.name ?? "Equipo visitante"}</div>
                </div>
              </div>
              {g.prediction ? (
                <>
                  <div className="prob-bar">
                    <div className="prob-fill-home" style={{ width: `${g.prediction.home_win_prob * 100}%` }} />
                    <div className="prob-fill-away" style={{ width: `${(1 - g.prediction.home_win_prob) * 100}%` }} />
                  </div>
                  <div className="prob-labels">
                    <span><strong>{Math.round(g.prediction.home_win_prob * 100)}%</strong> local</span>
                    <span><strong>{Math.round((1 - g.prediction.home_win_prob) * 100)}%</strong> visitante</span>
                  </div>
                </>
              ) : (
                <div className="prob-labels" style={{ justifyContent: "center", marginTop: 12 }}>
                  Sin predicción todavía
                </div>
              )}
            </a>
          ))
        )}
      </div>

      {/* ---------- Última jornada jugada ---------- */}
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Última jornada jugada
        </div>
        {lastJornada.length === 0 ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
            Todavía no se ha jugado ningún partido en esta temporada.
          </p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Local</th>
                  <th className="num">Marcador</th>
                  <th>Visitante</th>
                </tr>
              </thead>
              <tbody>
                {lastJornada.map((g) => {
                  const homeWon = g.homeScore > g.awayScore;
                  return (
                    <tr key={g.gameId} className="linked">
                      <td style={{ whiteSpace: "nowrap" }}>
                        <a href={`/partidos/${g.gameId}`}>
                          {new Date(g.date).toLocaleDateString("es-ES", { day: "2-digit", month: "short" })}
                        </a>
                      </td>
                      <td>
                        <a href={`/partidos/${g.gameId}`} style={{ display: "block" }}>
                          <TeamInline teamId={g.home?.id ?? 0} name={g.home?.name ?? "Local"} size={20} bold={homeWon} />
                        </a>
                      </td>
                      <td className="num" style={{ whiteSpace: "nowrap" }}>
                        <a href={`/partidos/${g.gameId}`}>
                          <span style={{ fontWeight: homeWon ? 700 : 400 }}>{g.homeScore}</span>
                          {" – "}
                          <span style={{ fontWeight: !homeWon ? 700 : 400 }}>{g.awayScore}</span>
                        </a>
                      </td>
                      <td>
                        <a href={`/partidos/${g.gameId}`} style={{ display: "block" }}>
                          <TeamInline teamId={g.away?.id ?? 0} name={g.away?.name ?? "Visitante"} size={20} bold={!homeWon} />
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ---------- Todas las jornadas ---------- */}
      <div className="panel">
        <div className="section-title">
          <span className="dot" /> Todas las jornadas
        </div>
        {jornadas.length === 0 ? (
          <p style={{ color: "var(--chalk-dim)", fontSize: 14 }}>
            Todavía no hay jornadas jugadas en esta temporada.
          </p>
        ) : (
          <div className="card-grid">
            {jornadas.map((j) => (
              <a
                key={j.number}
                href={`/temporadas/${encodeURIComponent(season)}/jornada/${j.number}`}
                className="tile"
              >
                <div className="tile-title" style={{ fontSize: 14 }}>{j.label}</div>
                <div className="tile-sub">{j.dateRange} · {j.games.length} partidos</div>
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