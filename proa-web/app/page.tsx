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

const TWO_DAYS_MS = 2 * 24 * 60 * 60 * 1000;

async function getUpcomingByMatchday(): Promise<Matchday[]> {
  const seasons = await getSeasons();
  const season = seasons[0];
  if (!season) return [];

  // Traemos TODO el calendario de la temporada (jugados y pendientes), no
  // solo los "scheduled" con fecha futura. Antes, en cuanto pasaba la hora
  // de un partido de hoy (jugado o no), desaparecía de la portada aunque la
  // jornada siguiente ni se acercara todavía. Con el calendario completo
  // podemos reconstruir las jornadas reales y decidir cuál enseñar según la
  // fecha de la SIGUIENTE jornada, no según cada partido suelto.
  const { data: allGames } = await supabase
    .from("games")
    .select("*")
    .eq("season", season)
    .order("date", { ascending: true })
    .range(0, 4999);

  if (!allGames || allGames.length === 0) return [];

  const teamIdsSet = new Set<number>();
  for (const g of allGames) {
    teamIdsSet.add(g.home_team_id);
    teamIdsSet.add(g.away_team_id);
  }
  const gamesPerMatchday = Math.max(1, Math.floor(teamIdsSet.size / 2));

  // Bloques cronológicos de tamaño "nº de equipos / 2" -- la misma
  // aproximación de jornada que ya se usa en /temporadas/[season]/jornada/[n]
  // y en /evolucion (Proballers no publica un número de jornada explícito).
  const jornadas: Game[][] = [];
  for (let i = 0; i < allGames.length; i += gamesPerMatchday) {
    jornadas.push(allGames.slice(i, i + gamesPerMatchday));
  }

  // Elegimos la jornada "actual" a mostrar: la más antigua cuya jornada
  // siguiente todavía no empieza dentro de 2 días. Así, la jornada de un
  // fin de semana se queda en portada -- con predicción y resultado si ya
  // ha terminado -- hasta 2 días antes del primer partido de la siguiente.
  let displayIndex = jornadas.length - 1;
  const now = new Date();
  for (let i = 0; i < jornadas.length - 1; i++) {
    const nextFirstDate = new Date(jornadas[i + 1][0].date);
    const cutoff = new Date(nextFirstDate.getTime() - TWO_DAYS_MS);
    if (now < cutoff) {
      displayIndex = i;
      break;
    }
  }

  const blocksToShow = jornadas.slice(displayIndex, displayIndex + 2);
  if (blocksToShow.length === 0) return [];

  const allShownGames = blocksToShow.flat();
  const teamIds = Array.from(
    new Set(allShownGames.flatMap((g) => [g.home_team_id, g.away_team_id]))
  );
  const gameIds = allShownGames.map((g) => g.id);

  const [{ data: teams }, { data: predictions }] = await Promise.all([
    supabase.from("teams").select("*").in("id", teamIds),
    supabase.from("predictions").select("*").in("game_id", gameIds),
  ]);

  const teamById = new Map((teams ?? []).map((t) => [t.id, t]));
  const predByGame = new Map((predictions ?? []).map((p) => [p.game_id, p]));

  const fmtDate = (d: string) =>
    new Date(d).toLocaleDateString("es-ES", { day: "2-digit", month: "short" });

  return blocksToShow.map((block, idx) => {
    const rows: Row[] = block.map((g) => ({
      ...g,
      home: teamById.get(g.home_team_id) ?? null,
      away: teamById.get(g.away_team_id) ?? null,
      prediction: predByGame.get(g.id) ?? null,
    }));
    const first = fmtDate(block[0].date);
    const last = fmtDate(block[block.length - 1].date);
    return {
      label: idx === 0 ? "Esta jornada" : "Próxima jornada",
      dateRange: first === last ? first : `${first} – ${last}`,
      games: rows,
    };
  });
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
          Predicciones del modelo para la jornada en curso y la siguiente de la
          Pro A. Haz clic en un partido para ver el resumen de ambos equipos.
        </p>
      </div>

      {matchdays.map((md, idx) => (
        <div key={idx} className="matchday-block">
          <div className="matchday-header">
            <span className="matchday-title">{md.label}</span>
            <span className="matchday-dates">{md.dateRange}</span>
          </div>
          {md.games.map((row) => {
            const isFinal =
              row.status === "final" && row.home_score != null && row.away_score != null;
            return (
              <a className="panel game-link" key={row.id} href={`/partidos/${row.id}`}>
                <div className="meta-row">
                  <span>
                    {new Date(row.date).toLocaleDateString("es-ES", {
                      weekday: "short",
                      day: "2-digit",
                      month: "short",
                    })}
                    {isFinal ? " · Finalizado" : ""}
                  </span>
                </div>

                <div className="matchup">
                  <div className="matchup-team">
                    {row.home && <TeamLogo teamId={row.home.id} name={row.home.name} size={26} />}
                    <div className="team-name">{row.home?.name ?? "Equipo local"}</div>
                  </div>
                  <div className="vs">
                    {isFinal ? (
                      <span className="scorefont" style={{ fontSize: 16, color: "var(--chalk)" }}>
                        {row.home_score} – {row.away_score}
                      </span>
                    ) : (
                      "vs"
                    )}
                  </div>
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
            );
          })}
        </div>
      ))}
    </div>
  );
}
