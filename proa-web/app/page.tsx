import { supabase, Game, Team, Prediction } from "@/lib/supabase";
import { TeamLogo } from "@/lib/team-logo";
import { getSeasons } from "@/lib/stats";

export const revalidate = 300; // refresca cada 5 min

type Row = Game & {
  home: Team | null;
  away: Team | null;
  prediction: Prediction | null;
};

type Matchday = { label: string; dateRange: string; games: Row[] };

async function getUpcomingByMatchday(): Promise<Matchday[]> {
  const seasons = await getSeasons();
  const season = seasons[0];
  if (!season) return [];

  // Proballers no publica un número de jornada explícito en el calendario
  // (la columna `matchday` de la base de datos está siempre vacía porque
  // no hay de dónde sacarla al scrapear). Como aproximación razonable,
  // agrupamos los próximos partidos en bloques de "nº de equipos / 2"
  // -- el tamaño естándar de una jornada de liga en formato round-robin --
  // en vez de enseñar una lista plana larga.
  const { data: teamsThisSeason } = await supabase
    .from("games")
    .select("home_team_id, away_team_id")
    .eq("season", season)
    .range(0, 999);
  const teamIdsSet = new Set<number>();
  for (const g of teamsThisSeason ?? []) {
    teamIdsSet.add(g.home_team_id);
    teamIdsSet.add(g.away_team_id);
  }
  const gamesPerMatchday = Math.max(1, Math.floor(teamIdsSet.size / 2));

  // OJO: filtramos por fecha >= hoy además de por status='scheduled'.
  // Sin esto, algún partido antiguo de una temporada ya acabada que se
  // quedó sin resultado cargado (p. ej. porque el boxscore nunca se pudo
  // scrapear) aparece como "próximo partido" y se cuela el primero de la
  // lista, rompiendo el orden cronológico real.
  const todayIso = new Date().toISOString();
  const { data: games } = await supabase
    .from("games")
    .select("*")
    .eq("status", "scheduled")
    .eq("season", season)
    .gte("date", todayIso)
    .order("date", { ascending: true })
    .limit(gamesPerMatchday * 2);

  if (!games || games.length === 0) return [];

  const teamIds = Array.from(
    new Set(games.flatMap((g) => [g.home_team_id, g.away_team_id]))
  );
  const gameIds = games.map((g) => g.id);

  const [{ data: teams }, { data: predictions }] = await Promise.all([
    supabase.from("teams").select("*").in("id", teamIds),
    supabase.from("predictions").select("*").in("game_id", gameIds),
  ]);

  const teamById = new Map((teams ?? []).map((t) => [t.id, t]));
  const predByGame = new Map((predictions ?? []).map((p) => [p.game_id, p]));

  const rows: Row[] = games.map((g) => ({
    ...g,
    home: teamById.get(g.home_team_id) ?? null,
    away: teamById.get(g.away_team_id) ?? null,
    prediction: predByGame.get(g.id) ?? null,
  }));

  const fmtDate = (d: string) =>
    new Date(d).toLocaleDateString("es-ES", { day: "2-digit", month: "short" });

  const matchdays: Matchday[] = [];
  for (let i = 0; i < rows.length; i += gamesPerMatchday) {
    const chunk = rows.slice(i, i + gamesPerMatchday);
    if (chunk.length === 0) continue;
    const first = fmtDate(chunk[0].date);
    const last = fmtDate(chunk[chunk.length - 1].date);
    matchdays.push({
      label: i === 0 ? "Próxima jornada" : "Jornada siguiente",
      dateRange: first === last ? first : `${first} – ${last}`,
      games: chunk,
    });
  }
  return matchdays;
}

export default async function HomePage() {
  const matchdays = await getUpcomingByMatchday();

  if (matchdays.length === 0) {
    return (
      <div className="empty">
        <div className="digits">00 – 00</div>
        <p style={{ margin: 0, fontSize: 15 }}>
          Todavía no hay partidos ni predicciones cargadas.
        </p>
        <p style={{ marginTop: 6, fontSize: 13 }}>
          En cuanto la temporada empiece y corras el pipeline (
          <code>python pipeline.py</code>), esta pantalla se llenará sola.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">En directo</div>
        <h1 className="page-title">Próximos partidos</h1>
        <p className="page-sub">
          Predicciones del modelo para las próximas {matchdays.length} jornadas de la
          Pro A. Haz clic en un partido para ver el resumen de ambos equipos.
        </p>
      </div>

      {matchdays.map((md, idx) => (
        <div key={idx} className="matchday-block">
          <div className="matchday-header">
            <span className="matchday-title">{md.label}</span>
            <span className="matchday-dates">{md.dateRange}</span>
          </div>
          {md.games.map((row) => (
            <a className="panel game-link" key={row.id} href={`/partidos/${row.id}`}>
              <div className="meta-row">
                <span>
                  {new Date(row.date).toLocaleDateString("es-ES", {
                    weekday: "short",
                    day: "2-digit",
                    month: "short",
                  })}
                </span>
              </div>

              <div className="matchup">
                <div className="matchup-team">
                  {row.home && <TeamLogo teamId={row.home.id} name={row.home.name} size={26} />}
                  <div className="team-name">{row.home?.name ?? "Equipo local"}</div>
                </div>
                <div className="vs">vs</div>
                <div className="matchup-team away">
                  {row.away && <TeamLogo teamId={row.away.id} name={row.away.name} size={26} />}
                  <div className="team-name away">{row.away?.name ?? "Equipo visitante"}</div>
                </div>
              </div>

              {row.prediction ? (
                <>
                  <div className="prob-bar">
                    <div
                      className="prob-fill-home"
                      style={{ width: `${row.prediction.home_win_prob * 100}%` }}
                    />
                    <div
                      className="prob-fill-away"
                      style={{ width: `${(1 - row.prediction.home_win_prob) * 100}%` }}
                    />
                  </div>
                  <div className="prob-labels">
                    <span>
                      <strong>{Math.round(row.prediction.home_win_prob * 100)}%</strong> local
                    </span>
                    {row.prediction.predicted_margin != null && (
                      <span>
                        margen estimado{" "}
                        <strong>{row.prediction.predicted_margin.toFixed(1)}</strong>
                      </span>
                    )}
                    <span>
                      <strong>{Math.round((1 - row.prediction.home_win_prob) * 100)}%</strong> visitante
                    </span>
                  </div>
                </>
              ) : (
                <div className="prob-labels" style={{ justifyContent: "center", marginTop: 12 }}>
                  Sin predicción todavía
                </div>
              )}
            </a>
          ))}
        </div>
      ))}
    </div>
  );
}
