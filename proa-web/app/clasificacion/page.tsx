import { supabase, Team, TeamRating } from "@/lib/supabase";
import { TeamInline } from "@/lib/team-logo";
import { getSeasons } from "@/lib/stats";

export const revalidate = 300;

type Ranked = { team: Team; elo: number };

async function getRanking(): Promise<{ ranked: Ranked[]; season: string | null }> {
  const seasons = await getSeasons();
  const season = seasons[0] ?? null; // temporada más reciente
  if (!season) return { ranked: [], season: null };

  // OJO: antes se listaban TODOS los equipos que hubiera alguna vez en
  // `teams`, incluidos los ya descendidos/desaparecidos de temporadas
  // pasadas. Ahora nos quedamos solo con los que tienen algún partido en
  // la temporada más reciente, que son los que compiten esta temporada.
  const { data: gamesThisSeason } = await supabase
    .from("games")
    .select("home_team_id, away_team_id")
    .eq("season", season)
    .range(0, 999);

  const activeTeamIds = new Set<number>();
  for (const g of gamesThisSeason ?? []) {
    activeTeamIds.add(g.home_team_id);
    activeTeamIds.add(g.away_team_id);
  }

  // Si la temporada más reciente todavía no tiene ni calendario publicado
  // (0 filas en `games`), caemos a la temporada anterior más reciente que
  // sí tenga equipos, para no dejar la página vacía en pretemporada.
  if (activeTeamIds.size === 0) {
    for (let i = 1; i < seasons.length; i++) {
      const { data: fallbackGames } = await supabase
        .from("games")
        .select("home_team_id, away_team_id")
        .eq("season", seasons[i])
        .range(0, 999);
      for (const g of fallbackGames ?? []) {
        activeTeamIds.add(g.home_team_id);
        activeTeamIds.add(g.away_team_id);
      }
      if (activeTeamIds.size > 0) break;
    }
  }
  if (activeTeamIds.size === 0) return { ranked: [], season };

  const { data: teams } = await supabase
    .from("teams")
    .select("*")
    .in("id", Array.from(activeTeamIds));
  if (!teams || teams.length === 0) return { ranked: [], season };

  // Para cada equipo, cogemos su rating Elo más reciente.
  const { data: ratings } = await supabase
    .from("team_ratings")
    .select("*")
    .in("team_id", Array.from(activeTeamIds))
    .order("date", { ascending: false });

  const latestByTeam = new Map<number, TeamRating>();
  for (const r of ratings ?? []) {
    if (!latestByTeam.has(r.team_id)) latestByTeam.set(r.team_id, r);
  }

  const ranked = teams
    .map((team) => ({
      team,
      elo: latestByTeam.get(team.id)?.elo_pre_game ?? 1500,
    }))
    .sort((a, b) => b.elo - a.elo);

  return { ranked, season };
}

export default async function ClasificacionPage() {
  const { ranked, season } = await getRanking();

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
          Fuerza actual de cada equipo de la temporada {season} según el sistema Elo
          interno del predictor. Para la clasificación real (victorias y derrotas) por
          temporada, visita{" "}
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
                  <td>
                    <TeamInline teamId={r.team.id} name={r.team.name} size={22} />
                  </td>
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
