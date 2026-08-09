import { supabase, Game, Team, Prediction } from "@/lib/supabase";

export const revalidate = 300; // refresca cada 5 min

type Row = Game & {
  home: Team | null;
  away: Team | null;
  prediction: Prediction | null;
};

async function getUpcoming(): Promise<Row[]> {
  const { data: games } = await supabase
    .from("games")
    .select("*")
    .eq("status", "scheduled")
    .order("date", { ascending: true })
    .limit(20);

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

  return games.map((g) => ({
    ...g,
    home: teamById.get(g.home_team_id) ?? null,
    away: teamById.get(g.away_team_id) ?? null,
    prediction: predByGame.get(g.id) ?? null,
  }));
}

export default async function HomePage() {
  const rows = await getUpcoming();

  if (rows.length === 0) {
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
      {rows.map((row) => (
        <div className="panel" key={row.id}>
          <div className="meta-row">
            <span>
              {new Date(row.date).toLocaleDateString("es-ES", {
                weekday: "short",
                day: "2-digit",
                month: "short",
              })}
            </span>
            {row.matchday && <span>Jornada {row.matchday}</span>}
          </div>

          <div className="matchup">
            <div className="team-name">{row.home?.name ?? "Equipo local"}</div>
            <div className="vs">vs</div>
            <div className="team-name away">
              {row.away?.name ?? "Equipo visitante"}
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
        </div>
      ))}
    </div>
  );
}
