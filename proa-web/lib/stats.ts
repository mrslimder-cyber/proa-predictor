import {
  supabase,
  Team,
  Game,
  TeamGameStats,
  PlayerGameStats,
  Prediction,
} from "@/lib/supabase";

// Nº mínimo de partidos jugados para poder entrar en un ranking individual.
export const MIN_GAMES_PLAYER = 3;
// Nº mínimo de tiros libres intentados para entrar en el ranking de % TL.
export const MIN_FT_ATT_PLAYER = 2;

// ---------- Temporadas ----------

export async function getSeasons(): Promise<string[]> {
  // Usamos una función SQL (distinct_seasons) en vez de traer todas las
  // filas de `games` y sacar los valores distintos en el cliente: la API
  // de Supabase corta cualquier SELECT normal en ~1000 filas por proyecto
  // (db-max-rows), un límite que NO se puede saltar pidiendo un .range()
  // más grande desde el cliente. Con 1500+ partidos en la tabla, ese
  // corte se comía temporadas enteras (se vio en producción con
  // "2025-2026"). La función agrega en el propio servidor y devuelve solo
  // un puñado de filas (una por temporada), así que nunca choca con ese límite.
  const { data, error } = await supabase.rpc("distinct_seasons");
  if (error || !data) {
    // Red de seguridad por si la función RPC no existe todavía (p. ej. no
    // se aplicó la migración): recurrimos al método anterior, que al menos
    // funciona bien mientras la tabla tenga menos de ~1000 filas.
    const { data: fallback } = await supabase.from("games").select("season").range(0, 9999);
    const set = new Set((fallback ?? []).map((g) => g.season));
    return Array.from(set).sort((a, b) => b.localeCompare(a));
  }
  return data.map((row: { season: string }) => row.season);
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

export async function getTeamsById(ids: number[]): Promise<Map<number, Team>> {
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

// ---------- Resumen de partido (al hacer clic en un partido) ----------

const RECENT_FORM_GAMES = 8;

export type FormEntry = {
  gameId: number;
  date: string;
  opponent: Team | null;
  isHome: boolean;
  pts: number;
  oppPts: number;
  win: boolean;
};

export type MatchupTeamSummary = {
  team: Team;
  season: string; // temporada de la que salen estas stats (puede ser una anterior, ver fallback abajo)
  isFallbackSeason: boolean; // true si la temporada actual no tenía partidos jugados todavía
  record: { wins: number; losses: number };
  ptsForAvg: number | null;
  ptsAgainstAvg: number | null;
  efgAvg: number | null;
  recentForm: FormEntry[]; // ordenados del más antiguo al más reciente
};

export type MatchupPreview = {
  game: Game;
  home: MatchupTeamSummary;
  away: MatchupTeamSummary;
  prediction: Prediction | null;
};

async function getFinishedTeamGames(
  season: string,
  teamId: number,
  beforeDate?: string
): Promise<Game[]> {
  let query = supabase
    .from("games")
    .select("*")
    .eq("season", season)
    .eq("status", "final")
    .or(`home_team_id.eq.${teamId},away_team_id.eq.${teamId}`)
    .order("date", { ascending: true })
    .range(0, 999);
  if (beforeDate) query = query.lt("date", beforeDate);
  const { data } = await query;
  return data ?? [];
}

async function buildTeamSummary(
  currentSeason: string,
  team: Team,
  beforeDate: string,
  allSeasonsDesc: string[]
): Promise<MatchupTeamSummary> {
  let season = currentSeason;
  let games = await getFinishedTeamGames(season, team.id, beforeDate);
  let isFallbackSeason = false;

  // En pretemporada (o al inicio de la temporada), un equipo puede no tener
  // TODAVÍA ningún partido jugado en `currentSeason`. En vez de enseñar un
  // resumen vacío, caemos a la temporada anterior más reciente en la que
  // ese equipo sí jugó, para que la página siempre tenga algo útil que mostrar.
  if (games.length === 0) {
    const idx = allSeasonsDesc.indexOf(currentSeason);
    for (let i = idx + 1; i < allSeasonsDesc.length; i++) {
      const fallbackGames = await getFinishedTeamGames(allSeasonsDesc[i], team.id);
      if (fallbackGames.length > 0) {
        games = fallbackGames;
        season = allSeasonsDesc[i];
        isFallbackSeason = true;
        break;
      }
    }
  }

  const gameIds = games.map((g) => g.id);
  const opponentIds = Array.from(
    new Set(
      games.map((g) => (g.home_team_id === team.id ? g.away_team_id : g.home_team_id))
    )
  );
  const [ownStats, opponentTeams] = await Promise.all([
    gameIds.length
      ? supabase.from("team_game_stats").select("efg_pct").eq("team_id", team.id).in("game_id", gameIds)
      : Promise.resolve({ data: [] as { efg_pct: number | null }[] }),
    getTeamsById(opponentIds),
  ]);

  let wins = 0;
  let losses = 0;
  let ptsFor = 0;
  let ptsAgainst = 0;
  const recentForm: FormEntry[] = [];

  for (const g of games) {
    const isHome = g.home_team_id === team.id;
    const pts = isHome ? g.home_score : g.away_score;
    const oppPts = isHome ? g.away_score : g.home_score;
    if (pts == null || oppPts == null) continue;
    const win = pts > oppPts;
    win ? wins++ : losses++;
    ptsFor += pts;
    ptsAgainst += oppPts;
    const oppId = isHome ? g.away_team_id : g.home_team_id;
    recentForm.push({
      gameId: g.id,
      date: g.date,
      opponent: opponentTeams.get(oppId) ?? null,
      isHome,
      pts,
      oppPts,
      win,
    });
  }

  const played = wins + losses;
  const efgVals = (ownStats.data ?? [])
    .map((s) => s.efg_pct)
    .filter((v): v is number => v != null);

  return {
    team,
    season,
    isFallbackSeason,
    record: { wins, losses },
    ptsForAvg: played > 0 ? ptsFor / played : null,
    ptsAgainstAvg: played > 0 ? ptsAgainst / played : null,
    efgAvg: efgVals.length > 0 ? efgVals.reduce((a, b) => a + b, 0) / efgVals.length : null,
    recentForm: recentForm.slice(-RECENT_FORM_GAMES),
  };
}

export async function getMatchupPreview(gameId: number): Promise<MatchupPreview | null> {
  const { data: game } = await supabase.from("games").select("*").eq("id", gameId).maybeSingle();
  if (!game) return null;

  const [teamById, { data: predictions }, allSeasonsDesc] = await Promise.all([
    getTeamsById([game.home_team_id, game.away_team_id]),
    supabase
      .from("predictions")
      .select("*")
      .eq("game_id", gameId)
      .order("created_at", { ascending: false })
      .limit(1),
    getSeasons(),
  ]);

  const homeTeam = teamById.get(game.home_team_id);
  const awayTeam = teamById.get(game.away_team_id);
  if (!homeTeam || !awayTeam) return null;

  // Partidos ya jugados en la fecha de este encuentro (o hasta "ahora" si es futuro),
  // para no meter datos del propio partido a predecir en su propio resumen.
  const cutoffDate = game.date;

  const [home, away] = await Promise.all([
    buildTeamSummary(game.season, homeTeam, cutoffDate, allSeasonsDesc),
    buildTeamSummary(game.season, awayTeam, cutoffDate, allSeasonsDesc),
  ]);

  return {
    game,
    home,
    away,
    prediction: predictions?.[0] ?? null,
  };
}