import { getSeasons, getSeasonSummary } from "@/lib/stats";

export const revalidate = 300;

export default async function TemporadasPage() {
  const seasons = await getSeasons();

  if (seasons.length === 0) {
    return (
      <div className="empty">
        <div className="digits">— · —</div>
        <p style={{ margin: 0, fontSize: 15 }}>
          Todavía no hay temporadas cargadas en la base de datos.
        </p>
      </div>
    );
  }

  const summaries = await Promise.all(
    seasons.map(async (s) => ({ season: s, ...(await getSeasonSummary(s)) }))
  );

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Histórico</div>
        <h1 className="page-title">Temporadas</h1>
        <p className="page-sub">
          Elige una temporada para ver la clasificación, los líderes estadísticos
          y el detalle de cada equipo.
        </p>
      </div>

      <div className="card-grid">
        {summaries.map((s) => (
          <a key={s.season} href={`/temporadas/${encodeURIComponent(s.season)}`} className="tile">
            <div className="tile-title">{s.season}</div>
            <div className="tile-sub">
              {s.playedGames} de {s.totalGames} partidos jugados
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
