from datetime import datetime
from scraper.realgm_scraper import get_games_for_date, get_boxscore

games = get_games_for_date(datetime(2025, 10, 5))
print(len(games), "partidos")

for g in games:
    box = get_boxscore(g["boxscore_url"])
    print(g["home_team_name"], box["home_score"], "-", box["away_score"], g["away_team_name"])
    for ts in box["team_stats"]:
        print("   ", ts["team_id"], "is_home:", ts["is_home"], "pts:", ts["pts"])