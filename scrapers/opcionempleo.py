"""
OpcionEmpleo Venezuela scraper — Venezuelan job board.
"""
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.opcionempleo.com.ve"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-VE,es;q=0.9",
}


def search(keywords: str = "marketing") -> list[dict]:
    results, seen = [], set()
    for kw in keywords.replace(",", " ").split():
        kw = kw.strip()
        if kw:
            results += _scrape(kw, seen)
    return results


def _scrape(keyword: str, seen: set) -> list[dict]:
    for url in [
        f"{BASE_URL}/buscar.php?q={keyword}",
        f"{BASE_URL}/trabajo/{keyword}",
        f"{BASE_URL}/empleos-de-{keyword}.html",
    ]:
        jobs = _try_url(url, keyword, seen)
        if jobs:
            return jobs
    return []


def _try_url(url: str, keyword: str, seen: set) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = (
            soup.select("article.job")
            or soup.select(".job-listing")
            or soup.select(".vacancy, .oferta")
            or soup.select("div[class*='job']")
        )
        if not cards:
            return []

        jobs = []
        for card in cards[:20]:
            link_el = (
                card.select_one("a[href*='/job/']")
                or card.select_one("a[href*='/trabajo/']")
                or card.select_one("h2 a, h3 a, h4 a")
            )
            if not link_el:
                continue

            href = link_el.get("href", "")
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            ext_id = re.sub(r"[^a-zA-Z0-9]", "", href)[-25:]

            if ext_id in seen:
                continue
            seen.add(ext_id)

            title_el = card.select_one("h2, h3, h4, .job-title") or link_el
            company_el = card.select_one(".company, .employer, .empresa")
            loc_el = card.select_one(".location, .lugar, .ciudad")

            jobs.append({
                "source": "OpcionEmpleo",
                "external_id": ext_id,
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "Empresa desconocida",
                "location": loc_el.get_text(strip=True) if loc_el else "Venezuela",
                "job_type": "Presencial/Híbrido",
                "salary": "",
                "description": "",
                "url": full_url,
                "tags": [keyword],
            })
        return jobs
    except Exception as e:
        print(f"[OpcionEmpleo] {url}: {e}")
        return []
