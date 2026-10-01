import re
from curl_cffi import requests

URL = "https://basketball.realgm.com/international/league/94/German-Pro-A/scores/2025-10-05/94"
r = requests.get(URL, impersonate="chrome")
html = r.text
open("page_debug.html", "w", encoding="utf-8").write(html)

print("status:", r.status_code, "| tamaño:", len(html))
print("título:", re.findall(r"<title>(.*?)</title>", html, re.S)[:1])

games = sorted(set(re.findall(r'/international/(?:preview|boxscore)/[^"\s<>]+', html)))
print(f"\nenlaces de partido distintos: {len(games)}")
for g in games[:15]:
    print("  ", g)

teams = sorted(set(re.findall(r'/international/league/\d+/[^"\s<>]*?/team/\d+/[^"\s/<>]+', html)))
print(f"\nenlaces de equipo distintos: {len(teams)}")
for t in teams[:15]:
    print("  ", t)

for kw in ("No games", "no games", "Final", "Box Score", "Preview"):
    print(f"'{kw}' aparece {html.count(kw)} veces")