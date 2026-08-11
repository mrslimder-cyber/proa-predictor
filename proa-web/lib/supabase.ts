import { createClient } from "@supabase/supabase-js";

// Estas dos variables se rellenan en .env.local (desarrollo) y en
// Vercel -> Settings -> Environment Variables (producción).
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// --- Tipos, en espejo de db/models.py del pipeline en Python ---

export type Team = {
  id: number;
  name: string;
  slug: string;
  season: string;
};

export type Game = {
  id: number;
  season: string;
  date: string;
  matchday: number | null;
  home_team_id: number;
  away_team_id: number;
  home_score: number | null;
  away_score: number | null;
  status: "scheduled" | "final";
};

export type Prediction = {
  id: number;
  game_id: number;
  model_version: string;
  home_win_prob: number;
  predicted_margin: number | null;
  created_at: string;
};

export type TeamRating = {
  id: number;
  team_id: number;
  game_id: number;
  date: string;
  elo_pre_game: number;
};

export type TeamGameStats = {
  id: number;
  game_id: number;
  team_id: number;
  is_home: boolean;
  fg2_made: number | null;
  fg2_att: number | null;
  fg3_made: number | null;
  fg3_att: number | null;
  ft_made: number | null;
  ft_att: number | null;
  oreb: number | null;
  dreb: number | null;
  reb: number | null;
  ast: number | null;
  tov: number | null;
  stl: number | null;
  blk: number | null;
  pf: number | null;
  pts: number | null;
  efg_pct: number | null;
  tov_pct: number | null;
  orb_pct: number | null;
  ft_rate: number | null;
};

export type PlayerGameStats = {
  id: number;
  game_id: number;
  team_id: number;
  player_id: number;
  player_name: string;
  minutes: number | null;
  pts: number | null;
  reb: number | null;
  ast: number | null;
  stl: number | null;
  blk: number | null;
  tov: number | null;
  pf: number | null;
  valuation: number | null;
  fg2_made: number | null;
  fg2_att: number | null;
  fg3_made: number | null;
  fg3_att: number | null;
  ft_made: number | null;
  ft_att: number | null;
};
