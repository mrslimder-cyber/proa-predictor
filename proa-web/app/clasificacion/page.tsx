import { supabase, Team, TeamRating } from "@/lib/supabase";

export const revalidate = 300;

type Ranked = { team: Team; elo: number };

async function getRanking(): Promise<Ranked[]> {
  const { data: teams } = await supabase.from("teams").select("*");
  if (!teams || teams.length === 0) return [];

  // Para cada equipo, cogemos su rating Elo más reciente.
  const { data: ratings } = await supabase
    .from("team_ratings")
    .select("*")
    .order("date", { ascending: false });

  const latestByTeam = new Map<number, TeamRating>();
  for (const r of ratings ?? []) {
    if (!latestByTeam.has(r.team_id)) latestByTeam.set(r.team_id, r);
  }

  return teams
    .map((team) => ({
      team,
      elo: latestByTeam.get(team.id)?.elo_pre_game ?? 1500,
    }))
    .sort((a, b) => b.elo - a.elo);
}

export default async function ClasificacionPage() {
  const ranked = await getRanking();

  if (ranked.length === 0) {
    return (
      <div className="empty">
        <div className="digits">— · —</div>
        <p style={{ margin: 0, fontSize: 15 }}>
          Todavía no hay equipos ni ratings Elo en la base de datos.
        </p>
        <p style={{ marginTop: 6, fontSize: 13 }}>
          Se rellena en cuanto corra <code>scraper.ingest</code> con los
          primeros partidos de la temporada.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Rating del modelo</div>
        <h1 className="page-title">Ranking Elo</h1>
        <p className="page-sub">
          Fuerza actual de cada equipo según el sistema Elo interno del predictor.
          Para la clasificación real (victorias y derrotas) por temporada, visita{" "}
          <a href="/temporadas" style={{ color: "var(--amber)", fontWeight: 600 }}>
            Temporadas
          </a>
          .
        </p>
      </div>
      <div className="panel">
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Equipo</th>
                <th>Elo</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((r, i) => (
                <tr key={r.team.id}>
                  <td className="num">
                    <span className={`rank-badge ${i === 0 ? "top1" : i === 1 ? "top2" : i === 2 ? "top3" : ""}`}>
                      {i + 1}
                    </span>
                  </td>
                  <td>{r.team.name}</td>
                  <td className="num">{Math.round(r.elo)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
