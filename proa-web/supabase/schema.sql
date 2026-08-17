-- Esquema para Supabase (Postgres), espejo exacto de db/models.py
-- del pipeline en Python. Pégalo en Supabase -> SQL Editor -> Run.

-- Una fila por equipo (id de Proballers, estable entre temporadas), no
-- una fila por (equipo, temporada). `season` guarda la última temporada
-- en la que se ha visto a ese equipo.
create table if not exists teams (
  id integer primary key,
  name text not null,
  slug text not null,
  season text not null
);

create table if not exists games (
  id integer primary key,
  season text not null,
  date timestamp not null,
  matchday integer,
  home_team_id integer not null,
  away_team_id integer not null,
  home_score integer,
  away_score integer,
  status text default 'scheduled',
  scraped_at timestamp default now()
);

create table if not exists team_game_stats (
  id serial primary key,
  game_id integer references games(id),
  team_id integer not null,
  is_home boolean not null,
  fg2_made integer, fg2_att integer,
  fg3_made integer, fg3_att integer,
  ft_made integer, ft_att integer,
  oreb integer, dreb integer, reb integer,
  ast integer, tov integer, stl integer, blk integer, pf integer, pts integer,
  efg_pct float, tov_pct float, orb_pct float, ft_rate float,
  unique (game_id, team_id)
);

create table if not exists player_game_stats (
  id serial primary key,
  game_id integer references games(id),
  team_id integer not null,
  player_id integer not null,
  player_name text not null,
  minutes float, pts integer, reb integer, ast integer,
  stl integer, blk integer, tov integer, pf integer, valuation integer,
  fg2_made integer, fg2_att integer,
  fg3_made integer, fg3_att integer,
  ft_made integer, ft_att integer
);

create table if not exists team_ratings (
  id serial primary key,
  team_id integer not null,
  game_id integer references games(id),
  date timestamp not null,
  elo_pre_game float not null,
  unique (team_id, game_id)
);

create table if not exists predictions (
  id serial primary key,
  game_id integer references games(id),
  model_version text not null,
  home_win_prob float not null,
  predicted_margin float,
  created_at timestamp default now(),
  unique (game_id, model_version)
);

-- Lectura pública (son datos de un modelo, no info sensible).
-- Si prefieres restringir, ajusta estas políticas.
alter table teams enable row level security;
alter table games enable row level security;
alter table predictions enable row level security;
alter table team_ratings enable row level security;

create policy "public read teams" on teams for select using (true);
create policy "public read games" on games for select using (true);
create policy "public read predictions" on predictions for select using (true);
create policy "public read team_ratings" on team_ratings for select using (true);

-- Devuelve las temporadas distintas presentes en `games`.
-- La usamos desde la web en vez de un SELECT normal porque la API de
-- Supabase corta cualquier consulta a ~1000 filas por proyecto
-- (db-max-rows), un límite que un .range() más grande desde el cliente
-- NO puede saltarse. Con varias temporadas de ~306 partidos cada una se
-- supera ese límite fácilmente, y el recorte puede comerse temporadas
-- enteras del listado. Al agregar en el propio servidor, esta función
-- solo devuelve un puñado de filas (una por temporada) y nunca choca
-- con ese límite.
create or replace function public.distinct_seasons()
returns table(season text)
language sql
stable
as $$
  select distinct games.season
  from public.games
  order by games.season desc;
$$;

grant execute on function public.distinct_seasons() to anon, authenticated;
