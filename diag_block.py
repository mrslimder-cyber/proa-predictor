import re

html = open("page_debug.html", encoding="utf-8").read()

i = html.find("/international/boxscore/2025-10-05/Eisbaren")
print("=== HTML alrededor del primer partido ===")
print(html[max(0, i - 1500): i + 500])

print("\n=== todos los href que contienen 'team' y NO son del menú de ligas ===")
hrefs = sorted(set(re.findall(r'href="([^"]*team[^"]*)"', html)))
for h in hrefs:
    if "/league/94/" in h or "/international/team/" in h or "Pro-A" in h:
        print("  ", h)