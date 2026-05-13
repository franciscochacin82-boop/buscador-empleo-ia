"""
Computrabajo Venezuela scraper — largest job board in Latin America.
"""
import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.computrabajo.com.ve"
SEARCH_URL = f"{BASE_URL}/trabajo-de-{{keyword}}"

KEYWORDS = ["marketing", "comunicaciones", "relaciones-publicas", "community-manager", "publicidad"]


def search() -> list[dict]:
    results = []
    seen = set()
    for kw in KEYWORDS:
        results += _scrape(kw, seen)
    return results


def _scrape(keyword: str, seen: set) -> list[dict]:
    try:
        url = SEARCH_URL.format(keyword=keyword)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-VE,es;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        job_cards = soup.select("article.box_offer") or soup.select("div[data-cs-company]")

        jobs = []
        for card in job_cards[:20]:
            link_el = card.select_one("a[href*='/oferta-de-trabajo']") or card.select_one("h2 a")
            if not link_el:
                continue

            href = link_el.get("href", "")
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            ext_id = re.search(r"/oferta-de-trabajo/([^/]+)", href)
            ext_id = ext_id.group(1) if ext_id else href[-30:]

            if ext_id in seen:
                continue
            seen.add(ext_id)

            title = link_el.get_text(strip=True)
            company_el = card.select_one("a[href*='/empresa/']") or card.select_one("p.fc_base")
            company = company_el.get_text(strip=True) if company_el else "Empresa desconocida"

            loc_el = card.select_one("span.fs16") or card.select_one("p.fs16")
            location = loc_el.get_text(strip=True) if loc_el else "Venezuela"

            jobs.append({
                "source": "Computrabajo",
                "external_id": ext_id,
                "title": title,
                "company": company,
                "location": location,
                "job_type": "Presencial/Híbrido",
                "salary": "",
                "description": "",
                "url": full_url,
                "tags": [keyword.replace("-", " ")],
            })
        return jobs
    except Exception as e:
        print(f"[Computrabajo] Error {keyword}: {e}")
        return []
