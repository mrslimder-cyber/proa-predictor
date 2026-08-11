import {
  supabase,
  Team,
  Game,
  TeamGameStats,
  PlayerGameStats,
} from "@/lib/supabase";

// Nº mínimo de partidos jugados para poder entrar en un ranking individual.
export const MIN_GAMES_PLAYER = 3;
// Nº mínimo de tiros libres intentados para entrar en el ranking de % TL.
export const MIN_FT_ATT_PLAYER = 0;

// ---------- Temporadas ----------

export async function getSeasons(): Promise<string[]> {
  const { data } = await supabase.from("games").select("season");
  const set = new Set((data ?? []).map((g) => g.season));
  return Array.from(set).sort((a, b) => b.localeCompare(a)); // más reciente primero
}

export async function getSeasonSummary(season: string) {
  const { data: games } = await supabase
    .from("games")
    .select("id,status")
    .eq("season", season);

  const total = games?.length ?? 0;
  const played = (games ?? []).filter((g) => g.status === "final").length;
  return { totalGames: total, playedGames: played };
}

// ---------- Utilidades internas ----------

async function getSeasonGames(season: string): Promise<Game[]> {
  const { data } = await supabase
    .from("games")
    .select("*")
    .eq("season", season)
    .eq("status", "final")
    .range(0, 4999);
  return data ?? [];
}

async function getTeamStatsForGames(
  gameIds: number[]
): Promise<TeamGameStats[]> {
  if (gameIds.length === 0) return [];
  const { data } = await supabase
    .from("team_game_stats")
    .select("*")
    .in("game_id", gameIds)
    .range(0, 4999);
  return data ?? [];
}

async function getPlayerStatsForGames(
  gameIds: number[]
): Promise<PlayerGameStats[]> {
  if (gameIds.length === 0) return [];
  const { data } = await supabase
    .from("player_game_stats")
    .select("*")
    .in("game_id", gameIds)
    .range(0, 9999);
  return data ?? [];
}

async function getTeamsById(ids: number[]): Promise<Map<number, Team>> {
  if (ids.length === 0) return new Map();
  const { data } = await supabase.from("teams").select("*").in("id", ids);
  return new Map((data ?? []).map((t) => [t.id, t]));
}

// ---------- Clasificación (standings) ----------

export type StandingRow = {
  team: Team;
  played: number;
  wins: number;
  losses: number;
  pf: number; // puntos a favor
  pa: number; // puntos en contra
  diff: number;
  winPct: number;
};

export async function getStandings(season: string): Promise<StandingRow[]> {
  const games = await getSeasonGames(season);
  if (games.length === 0) return [];

  const teamIds = Array.from(
    new Set(games.flatMap((g) => [g.home_team_id, g.away_team_id]))
  );
  const teamById = await getTeamsById(teamIds);

  const acc = new Map<
    number,
    { played: number; wins: number; losses: number; pf: number; pa: number }
  >();
  const ensure = (id: number) => {
    if (!acc.has(id)) {
      acc.set(id, { played: 0, wins: 0, losses: 0, pf: 0, pa: 0 });
    }
    return acc.get(id)!;
  };

  for (const g of games) {
    if (g.home_score == null || g.away_score == null) continue;
    const home = ensure(g.home_team_id);
    const away = ensure(g.away_team_id);
    home.played += 1;
    away.played += 1;
    home.pf += g.home_score;
    home.pa += g.away_score;
    away.pf += g.away_score;
    away.pa += g.home_score;
    if (g.home_score > g.away_score) {
      home.wins += 1;
      away.losses += 1;
    } else if (g.away_score > g.home_score) {
      away.wins += 1;
      home.losses += 1;
    }
  }

  const rows: StandingRow[] = [];
  for (const [teamId, s] of acc.entries()) {
    const team = teamById.get(teamId);
    if (!team) continue;
    rows.push({
      team,
      played: s.played,
      wins: s.wins,
      losses: s.losses,
      pf: s.pf,
      pa: s.pa,
      diff: s.pf - s.pa,
      winPct: s.played > 0 ? s.wins / s.played : 0,
    });
  }

  rows.sort((a, b) => b.winPct - a.winPct || b.diff - a.diff);
  return rows;
}

// ---------- Líderes de la temporada ----------

export type TeamLeaderRow = { team: Team; games: number; avg: number };
export type PlayerLeaderRow = {
  playerId: number;
  playerName: string;
  team: Team | null;
  games: number;
  avg: number; // pts o reb o ast promedio, según el ranking
  pct?: number; // % tiros libres, si aplica
};

export type SeasonLeaders = {
  teamPoints: TeamLeaderRow[];
  teamFtPct: (TeamLeaderRow & { pct: number })[];
  playerPoints: PlayerLeaderRow[];
  playerFtPct: PlayerLeaderRow[];
};

export async function getSeasonLeaders(season: string): Promise<SeasonLeaders> {
  const games = await getSeasonGames(season);
  const gameIds = games.map((g) => g.id);
  if (gameIds.length === 0) {
    return { teamPoints: [], teamFtPct: [], playerPoints: [], playerFtPct: [] };
  }

  const [teamStats, playerStats] = await Promise.all([
    getTeamStatsForGames(gameIds),
    getPlayerStatsForGames(gameIds),
  ]);

  const teamIds = Array.from(new Set(teamStats.map((t) => t.team_id)));
  const teamById = await getTeamsById(teamIds);

  // --- Equipos: puntos por partido ---
  const teamAcc = new Map<
    number,
    { games: number; pts: number; ftMade: number; ftAtt: number }
  >();
  for (const s of teamStats) {
    const e = teamAcc.get(s.team_id) ?? {
      games: 0,
      pts: 0,
      ftMade: 0,
      ftAtt: 0,
    };
    e.games += 1;
    e.pts += s.pts ?? 0;
    e.ftMade += s.ft_made ?? 0;
    e.ftAtt += s.ft_att ?? 0;
    teamAcc.set(s.team_id, e);
  }

  const teamPoints: TeamLeaderRow[] = [];
  const teamFtPct: (TeamLeaderRow & { pct: number })[] = [];
  for (const [id, e] of teamAcc.entries()) {
    const team = teamById.get(id);
    if (!team || e.games === 0) continue;
    teamPoints.push({ team, games: e.games, avg: e.pts / e.games });
    if (e.ftAtt >= 20) {
      teamFtPct.push({
        team,
        games: e.games,
        avg: e.pts / e.games,
        pct: e.ftMade / e.ftAtt,
      });
    }
  }
  teamPoints.sort((a, b) => b.avg - a.avg);
  teamFtPct.sort((a, b) => b.pct - a.pct);
  const teamPointsTop = teamPoints.slice(0, 8);
  const teamFtPctTop = teamFtPct.slice(0, 8);

  // --- Jugadores: puntos por partido y % tiros libres ---
  const playerAcc = new Map<
    number,
    {
      name: string;
      teamId: number;
      games: number;
      pts: number;
      ftMade: number;
      ftAtt: number;
    }
  >();
  for (const s of playerStats) {
    const e = playerAcc.get(s.player_id) ?? {
      name: s.player_name,
      teamId: s.team_id,
      games: 0,
      pts: 0,
      ftMade: 0,
      ftAtt: 0,
    };
    e.games += 1;
    e.pts += s.pts ?? 0;
    e.ftMade += s.ft_made ?? 0;
    e.ftAtt += s.ft_att ?? 0;
    // nos quedamos con el equipo más reciente (última vez que aparece)
    e.teamId = s.team_id;
    playerAcc.set(s.player_id, e);
  }

  const playerPoints: PlayerLeaderRow[] = [];
  const playerFtPct: PlayerLeaderRow[] = [];
  for (const [playerId, e] of playerAcc.entries()) {
    const team = teamById.get(e.teamId) ?? null;
    if (e.games >= MIN_GAMES_PLAYER) {
      playerPoints.push({
        playerId,
        playerName: e.name,
        team,
        games: e.games,
        avg: e.pts / e.games,
      });
      if (e.ftAtt >= MIN_FT_ATT_PLAYER) {
        playerFtPct.push({
          playerId,
          playerName: e.name,
          team,
          games: e.games,
          avg: e.pts / e.games,
          pct: e.ftMade / e.ftAtt,
        });
      }
    }
  }
  playerPoints.sort((a, b) => b.avg - a.avg);
  playerFtPct.sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0));
  const playerPointsTop = playerPoints.slice(0, 10);
  const playerFtPctTop = playerFtPct.slice(0, 10);

  return {
    teamPoints: teamPointsTop,
    teamFtPct: teamFtPctTop,
    playerPoints: playerPointsTop,
    playerFtPct: playerFtPctTop,
  };
}

// ---------- Detalle de equipo dentro de una temporada ----------

export type RosterRow = {
  playerId: number;
  playerName: string;
  games: number;
  ptsAvg: number;
  rebAvg: number;
  astAvg: number;
  ftPct: number | null;
  ftAtt: number;
};

export type TeamGameLog = {
  gameId: number;
  date: string;
  matchday: number | null;
  opponent: string;
  isHome: boolean;
  pts: number;
  oppPts: number;
  win: boolean;
};

export type TeamDetail = {
  team: Team;
  standing: StandingRow | null;
  roster: RosterRow[];
  topPoints: RosterRow[];
  topRebounds: RosterRow[];
  topAssists: RosterRow[];
  topFt: RosterRow[];
  gameLog: TeamGameLog[];
  seasonAvg: { pts: number; reb: number; ast: number; ftPct: number | null };
};

export async function getTeamDetail(
  season: string,
  teamId: number
): Promise<TeamDetail | null> {
  const [games, teamById, standings] = await Promise.all([
    getSeasonGames(season),
    getTeamsById([teamId]),
    getStandings(season),
  ]);

  const team = teamById.get(teamId);
  if (!team) return null;

  const teamGames = games.filter(
    (g) => g.home_team_id === teamId || g.away_team_id === teamId
  );
  const gameIds = teamGames.map((g) => g.id);

  const [teamStatsAll, playerStatsAll, opponentTeams] = await Promise.all([
    getTeamStatsForGames(gameIds),
    getPlayerStatsForGames(gameIds),
    getTeamsById(
      Array.from(
        new Set(
          teamGames.flatMap((g) => [g.home_team_id, g.away_team_id])
        )
      )
    ),
  ]);

  const ownTeamStats = teamStatsAll.filter((s) => s.team_id === teamId);
  const ownPlayerStats = playerStatsAll.filter((s) => s.team_id === teamId);

  // --- Game log (para el gráfico de evolución de puntos) ---
  const gameLog: TeamGameLog[] = [];
  for (const g of teamGames) {
    const isHome = g.home_team_id === teamId;
    const pts = isHome ? g.home_score : g.away_score;
    const oppPts = isHome ? g.away_score : g.home_score;
    const oppId = isHome ? g.away_team_id : g.home_team_id;
    if (pts == null || oppPts == null) continue;
    gameLog.push({
      gameId: g.id,
      date: g.date,
      matchday: g.matchday,
      opponent: opponentTeams.get(oppId)?.name ?? "Rival",
      isHome,
      pts,
      oppPts,
      win: pts > oppPts,
    });
  }
  gameLog.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  // --- Plantilla (roster) con medias por jugador ---
  const playerAcc = new Map<
    number,
    {
      name: string;
      games: number;
      pts: number;
      reb: number;
      ast: number;
      ftMade: number;
      ftAtt: number;
    }
  >();
  for (const s of ownPlayerStats) {
    const e = playerAcc.get(s.player_id) ?? {
      name: s.player_name,
      games: 0,
      pts: 0,
      reb: 0,
      ast: 0,
      ftMade: 0,
      ftAtt: 0,
    };
    e.games += 1;
    e.pts += s.pts ?? 0;
    e.reb += s.reb ?? 0;
    e.ast += s.ast ?? 0;
    e.ftMade += s.ft_made ?? 0;
    e.ftAtt += s.ft_att ?? 0;
    playerAcc.set(s.player_id, e);
  }

  const roster: RosterRow[] = Array.from(playerAcc.entries())
    .map(([playerId, e]) => ({
      playerId,
      playerName: e.name,
      games: e.games,
      ptsAvg: e.pts / e.games,
      rebAvg: e.reb / e.games,
      astAvg: e.ast / e.games,
      ftPct: e.ftAtt > 0 ? e.ftMade / e.ftAtt : null,
      ftAtt: e.ftAtt,
    }))
    .sort((a, b) => b.ptsAvg - a.ptsAvg);

  const eligible = roster.filter((r) => r.games >= MIN_GAMES_PLAYER);

  const topPoints = [...eligible].sort((a, b) => b.ptsAvg - a.ptsAvg).slice(0, 3);
  const topRebounds = [...eligible].sort((a, b) => b.rebAvg - a.rebAvg).slice(0, 3);
  const topAssists = [...eligible].sort((a, b) => b.astAvg - a.astAvg).slice(0, 3);
  const topFt = [...eligible]
    .filter((r) => r.ftAtt >= MIN_FT_ATT_PLAYER)
    .sort((a, b) => (b.ftPct ?? 0) - (a.ftPct ?? 0))
    .slice(0, 3);

  // --- Medias de equipo ---
  const teamTotals = ownTeamStats.reduce(
    (acc, s) => {
      acc.games += 1;
      acc.pts += s.pts ?? 0;
      acc.reb += s.reb ?? 0;
      acc.ast += s.ast ?? 0;
      acc.ftMade += s.ft_made ?? 0;
      acc.ftAtt += s.ft_att ?? 0;
      return acc;
    },
    { games: 0, pts: 0, reb: 0, ast: 0, ftMade: 0, ftAtt: 0 }
  );

  const seasonAvg = {
    pts: teamTotals.games ? teamTotals.pts / teamTotals.games : 0,
    reb: teamTotals.games ? teamTotals.reb / teamTotals.games : 0,
    ast: teamTotals.games ? teamTotals.ast / teamTotals.games : 0,
    ftPct: teamTotals.ftAtt > 0 ? teamTotals.ftMade / teamTotals.ftAtt : null,
  };

  const standing = standings.find((s) => s.team.id === teamId) ?? null;

  return {
    team,
    standing,
    roster,
    topPoints,
    topRebounds,
    topAssists,
    topFt,
    gameLog,
    seasonAvg,
  };
}

export async function getSeasonTeams(season: string): Promise<Team[]> {
  const standings = await getStandings(season);
  return standings.map((s) => s.team);
}