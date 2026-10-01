from scraper.realgm_scraper import get_boxscore

box = get_boxscore("https://basketball.realgm.com/international/boxscore/2025-10-05/Eisbaren-Bremerhaven-at-WWU-Baskets-Muenster/496206")
for p in box["player_stats"][:6]:
    print(p["player_name"], p["player_id"])