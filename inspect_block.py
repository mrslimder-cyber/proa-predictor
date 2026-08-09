# inspect_block.py — pégalo en proa-predictor/ y ejecútalo con: python inspect_block.py
import re
from scraper.proballers_scraper import _get, GAME_HREF_RE
from config import season_calendar_url

for season in ["2022-2023", "2025-2026"]:  # ajusta al histórico real que tengas
    print(f"\n=== {season} ===")
    soup = _get(season_calendar_url(season))
    link = soup.find("a", href=GAME_HREF_RE)
    block = link.find_parent(["div", "li", "article"])
    text = block.get_text(" ", strip=True)
    print("TEXTO:", text)
    print("Números 2-3 dígitos encontrados:", re.findall(r"\b(\d{2,3})\b", text))