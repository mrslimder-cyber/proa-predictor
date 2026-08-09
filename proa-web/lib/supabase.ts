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
