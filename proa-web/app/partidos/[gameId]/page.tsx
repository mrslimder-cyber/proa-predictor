import { notFound } from "next/navigation";
import { getMatchupPreview, MatchupTeamSummary } from "@/lib/stats";
import { TeamLogo } from "@/lib/team-logo";

export const revalidate = 300;

export default async function GameSummaryPage({
  params,
}: {
  params: { gameId: string };
}) {
  const gameId = Number(params.gameId);
  if (Number.isNaN(gameId)) notFound();

  const preview = await getMatchupPreview(gameId);
  if (!preview) notFound();

  const { game, home, away, prediction } = preview;
  const isFinal = game.status === "final";

  return (
    <div>
      <div className="breadcrumb">
        <a href="/">Próximos partidos</a>
        <span className="sep">/</span>
        <span className="current">
          {home.team.name} vs {away.team.name}
        </span>
      </div>

      <div className="panel">
        <div className="meta-row" style={{ justifyContent: "center", marginBottom: 4 }}>
          <span>
            {new Date(game.date).toLocaleDateString("es-ES", {
              weekday: "long",
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
            {game.matchday ? ` · Jornada ${game.matchday}` : ""}
            {isFinal ? " · Finalizado" : ""}
          </span>
        </div>

        <div className="matchup-hero">
          <div className="matchup-hero-team">
            <TeamLogo teamId={home.team.id} name={home.team.name} size={56} />
            <div className="name">{home.team.name}</div>
          </div>
          <div className="matchup-hero-vs">
            {isFinal && game.home_score != null && game.away_score != null ? (
              <span className="scorefont" style={{ fontSize: 26, color: "var(--chalk)" }}>
                {game.home_score} – {game.away_score}
              </span>
            ) : (
              "VS"
            )}
          </div>
          <div className="matchup-hero-team">
            <TeamLogo teamId={away.team.id} name={away.team.name} size={56} />
            <div className="name">{away.team.name}</div>
          </div>
        </div>

        {prediction ? (
          <>
            <div className="prob-bar" style={{ marginTop: 18 }}>
              <div
                className="prob-fill-home"
                style={{ width: `${prediction.home_win_prob * 100}%` }}
              />
              <div
                className="prob-fill-away"
                style={{ width: `${(1 - prediction.home_win_prob) * 100}%` }}
              />
            </div>
            <div className="prob-labels">
              <span>
                <strong>{Math.round(prediction.home_win_prob * 100)}%</strong> local
              </span>
              {prediction.predicted_margin != null && (
                <span>
                  margen estimado <strong>{prediction.predicted_margin.toFixed(1)}</strong>
                </span>
              )}
              <span>
                <strong>{Math.round((1 - prediction.home_win_prob) * 100)}%</strong> visitante
              </span>
            </div>
          </>
        ) : (
          <div className="prob-labels" style={{ justifyContent: "center", marginTop: 14 }}>
            Sin predicción todavía
          </div>
        )}
      </div>

      <div className="summary-grid">
        <TeamSummaryCard summary={home} />
        <TeamSummaryCard summary={away} />
      </div>
    </div>
  );
}

function TeamSummaryCard({ summary }: { summary: MatchupTeamSummary }) {
  const { team, season, isFallbackSeason, record, ptsForAvg, ptsAgainstAvg, efgAvg, recentForm } =
    summary;

  return (
    <div className="panel">
      <div className="section-title">
        <span className="dot" />
        <a
          href={`/temporadas/${encodeURIComponent(season)}/equipos/${team.id}`}
          style={{ display: "flex", alignItems: "center", gap: 8 }}
        >
          <TeamLogo teamId={team.id} name={team.name} size={20} />
          {team.name}
        </a>
      </div>

      {recentForm.length === 0 ? (
        <p style={{ color: "var(--chalk-dim)", fontSize: 13.5 }}>
          Este equipo todavía no tiene partidos jugados con datos suficientes.
        </p>
      ) : (
        <>
          <div className="pill-row">
            <div className="stat-pill">
              <div className="label">Récord</div>
              <div className="value">
                {record.wins}-{record.losses}
              </div>
            </div>
            <div className="stat-pill">
              <div className="label">Pts a favor</div>
              <div className="value">{ptsForAvg != null ? ptsForAvg.toFixed(1) : "—"}</div>
            </div>
            <div className="stat-pill">
              <div className="label">Pts en contra</div>
              <div className="value">{ptsAgainstAvg != null ? ptsAgainstAvg.toFixed(1) : "—"}</div>
            </div>
            <div className="stat-pill">
              <div className="label">eFG%</div>
              <div className="value">{efgAvg != null ? `${(efgAvg * 100).toFixed(1)}%` : "—"}</div>
            </div>
          </div>

          <div className="section-title" style={{ marginTop: 18 }}>
            Últimos {recentForm.length} partidos
          </div>
          <div className="form-row">
            {recentForm.map((f) => (
              <span
                key={f.gameId}
                className={`form-bubble ${f.win ? "win" : "loss"}`}
                title={`${f.isHome ? "vs" : "@"} ${f.opponent?.name ?? "Rival"}: ${f.pts}-${f.oppPts}`}
              >
                {f.win ? "W" : "L"}
              </span>
            ))}
          </div>

          {isFallbackSeason && (
            <p className="fallback-note">
              Todavía sin partidos jugados esta temporada — datos de la temporada {season}.
            </p>
          )}
        </>
      )}
    </div>
  );
}
