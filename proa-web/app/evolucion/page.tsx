import { getSeasons, getModelEvolution } from "@/lib/stats";
import SeasonPicker from "./season-picker";
import { EvolutionCharts } from "./evolution-charts";

export const revalidate = 300;

export default async function EvolucionPage({
  searchParams,
}: {
  searchParams: { season?: string };
}) {
  const seasons = await getSeasons();
  const season = searchParams.season && seasons.includes(searchParams.season)
    ? searchParams.season
    : seasons[0];

  if (!season) {
    return (
      <div className="empty">
        <div className="digits">— · —</div>
        <p>Todavía no hay temporadas con datos.</p>
      </div>
    );
  }

  const jornadas = await getModelEvolution(season);

  return (
    <div>
      <div className="page-header">
        <div className="eyebrow">Rendimiento del modelo</div>
        <h1 className="page-title">Evolución</h1>
        <p className="page-sub">
          Cómo de bien predijo el modelo cada jornada ya jugada: acierto en el
          ganador y margen estimado frente al real.
        </p>
      </div>

      <div className="select-row">
        <SeasonPicker seasons={seasons} current={season} />
      </div>

      {jornadas.length === 0 ? (
        <div className="empty">
          <div className="digits">00%</div>
          <p>
            Todavía no hay partidos finalizados con predicción guardada para
            esta temporada (recuerda: la predicción tiene que haberse
            generado ANTES de que el partido se jugara).
          </p>
        </div>
      ) : (
        <EvolutionCharts jornadas={jornadas} />
      )}
    </div>
  );
}