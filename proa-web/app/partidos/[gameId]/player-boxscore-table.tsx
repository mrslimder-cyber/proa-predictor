import type { PlayerBoxscoreRow } from "@/lib/stats";

export function PlayerBoxscoreTable({
  teamName,
  players,
}: {
  teamName: string;
  players: PlayerBoxscoreRow[];
}) {
  return (
    <div className="panel">
      <div className="section-title">
        <span className="dot" /> {teamName} — jugadores
      </div>
      {players.length === 0 ? (
        <p style={{ color: "var(--chalk-dim)", fontSize: 13.5 }}>
          Sin estadísticas de jugadores guardadas para este partido.
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Jugador</th>
                <th className="num">Min</th>
                <th className="num">Pts</th>
                <th className="num">Reb</th>
                <th className="num">Ast</th>
                <th className="num">Rob</th>
                <th className="num">Tap</th>
                <th className="num">BP</th>
                <th className="num">Val</th>
              </tr>
            </thead>
            <tbody>
              {players.map((p) => (
                <tr key={p.id}>
                  <td>{p.playerName}</td>
                  <td className="num">{p.minutes != null ? p.minutes.toFixed(0) : "—"}</td>
                  <td className="num">{p.pts ?? "—"}</td>
                  <td className="num">{p.reb ?? "—"}</td>
                  <td className="num">{p.ast ?? "—"}</td>
                  <td className="num">{p.stl ?? "—"}</td>
                  <td className="num">{p.blk ?? "—"}</td>
                  <td className="num">{p.tov ?? "—"}</td>
                  <td className="num">{p.valuation ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
