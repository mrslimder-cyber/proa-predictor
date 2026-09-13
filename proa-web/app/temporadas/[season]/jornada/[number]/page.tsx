import { notFound } from "next/navigation";
import { getSeasons, getJornadaGames } from "@/lib/stats";
import { TeamInline } from "@/lib/team-logo";

export const revalidate = 300;

export default async function JornadaPage({
  params,
}: {
  params: { season: string; number: string };
}) {
  const season = decodeURIComponent(params.season);
  const jornadaNumber = Number(params.number);
  if (Number.isNaN(jornadaNumber)) notFound();

  const seasons = await getSeasons();
  if (!seasons.includes(season)) notFound();

  const jornada = await getJornadaGames(season, jornadaNumber);
  if (!jornada) notFound();

  return (
    <div>
      <div className="breadcrumb">
        <a href="/temporadas">Temporadas</a>
        <span className="sep">/</span>
        <a href={`/temporadas/${encodeURIComponent(season)}`}>{season}</a>
        <span className="sep">/</span>
        <span className="current">{jornada.label}</span>
      </div>

      <div className="page-header">
        <div className="eyebrow">Temporada {season}</div>
        <h1 className="page-title">{jornada.label}</h1>
        <p className="page-sub">{jornada.dateRange} · {jornada.games.length} partidos</p>
      </div>

      <div className="panel">
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
              {jornada.games.map((g) => {
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
      </div>

      <div className="select-row" style={{ marginTop: 18, justifyContent: "space-between" }}>
        {jornadaNumber > 1 ? (
          <a className="season-select" href={`/temporadas/${encodeURIComponent(season)}/jornada/${jornadaNumber - 1}`}>
            ← Jornada {jornadaNumber - 1}
          </a>
        ) : <span />}
        <a className="season-select" href={`/temporadas/${encodeURIComponent(season)}/jornada/${jornadaNumber + 1}`}>
          Jornada {jornadaNumber + 1} →
        </a>
      </div>
    </div>
  );
}