"""
Glassdoor job scraper — uses their search page.
NOTE: Glassdoor heavily protects against scraping.
This works on a best-effort basis; returns empty list if blocked.
"""
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.glassdoor.com"
SEARCH_URL = f"{BASE_URL}/Job/jobs.htm"


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def search(keywords: str = "marketing", location: str = "") -> list[dict]:
    try:
        params = {
            "sc.keyword": keywords,
            "locT": "N",
            "suggestChosen": "false",
            "clickSource": "searchBtn",
        }
        if location:
            params["sc.location"] = location

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.glassdoor.com/",
        }
        resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = (
            soup.select("li.react-job-listing")
            or soup.select("[data-test='jobListing']")
            or soup.select(".JobCard_jobCardContent__o7Lph")
            or soup.select("article.JobCard")
        )

        jobs = []
        seen = set()
        for card in cards[:20]:
            link_el = card.select_one("a[href*='/job-listing/']") or card.select_one("a[data-test='job-link']")
            title_el = card.select_one("[data-test='job-title'], .JobCard_seoLink__WdqHZ, h3")
            company_el = card.select_one("[data-test='employer-name'], .EmployerProfile_compactEmployerName__9MGcV")
            loc_el = card.select_one("[data-test='emp-location'], .JobCard_location__rCz3x")

            if not title_el:
                continue

            href = link_el.get("href", "") if link_el else ""
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            ext_id = re.search(r"jobListingId=(\d+)", href)
            ext_id = ext_id.group(1) if ext_id else href[-20:]

            if ext_id in seen:
                continue
            seen.add(ext_id)

            jobs.append({
                "source": "Glassdoor",
                "external_id": ext_id,
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "Empresa desconocida",
                "location": loc_el.get_text(strip=True) if loc_el else (location or "No especificado"),
                "job_type": "",
                "salary": "",
                "description": "",
                "url": full_url,
                "tags": [],
            })
        return jobs
    except Exception as e:
        print(f"[Glassdoor] Error: {e}")
        return []
