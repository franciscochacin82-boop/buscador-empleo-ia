"""
Bumeran Venezuela — React SPA, requires Playwright for full scraping.
Falls back to their internal search API if available.
"""
import re
import requests

BASE_URL = "https://www.bumeran.com.ve"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-VE,es;q=0.9",
    "Referer": BASE_URL,
}

# Bumeran (Navent group) internal search API endpoints to try
API_ENDPOINTS = [
    "/api/postings/search",
    "/api/v1/jobs/search",
    "/candidate/api/postings",
]


def search(keywords: str = "marketing") -> list[dict]:
    jobs = _try_api(keywords)
    if jobs:
        return jobs
    # Playwright fallback (if installed)
    return _try_playwright(keywords)


def _try_api(keywords: str) -> list[dict]:
    for endpoint in API_ENDPOINTS:
        try:
            resp = requests.get(
                f"{BASE_URL}{endpoint}",
                params={"q": keywords, "size": 20, "from": 0},
                headers=HEADERS,
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                # Try to parse common response shapes
                items = (
                    data.get("postings")
                    or data.get("jobs")
                    or data.get("results")
                    or (data if isinstance(data, list) else [])
                )
                if items:
                    return _parse(items, keywords)
        except Exception:
            continue
    return []


def _parse(items: list, keyword: str) -> list[dict]:
    jobs = []
    for item in items[:20]:
        title = item.get("title") or item.get("name") or item.get("objective") or ""
        company = (
            item.get("company", {}).get("name")
            if isinstance(item.get("company"), dict)
            else item.get("company") or "Empresa desconocida"
        )
        ext_id = str(item.get("id") or item.get("publicId") or "")[:25]
        url_path = item.get("url") or item.get("link") or f"{BASE_URL}/empleo/{ext_id}"
        full_url = url_path if url_path.startswith("http") else f"{BASE_URL}{url_path}"
        jobs.append({
            "source": "Bumeran",
            "external_id": ext_id,
            "title": title,
            "company": company,
            "location": item.get("location", {}).get("description", "Venezuela")
                if isinstance(item.get("location"), dict) else "Venezuela",
            "job_type": "Presencial/Híbrido",
            "salary": "",
            "description": re.sub(r"<[^>]+>", " ", item.get("description") or "").strip(),
            "url": full_url,
            "tags": [keyword],
        })
    return jobs


def _try_playwright(keywords: str) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{BASE_URL}/empleos-busqueda-{keywords.split()[0]}.html", timeout=20000)
            page.wait_for_selector("[data-qa='posting-list-item'], .aviso", timeout=8000)

            cards = page.query_selector_all("[data-qa='posting-list-item'], .aviso")
            jobs = []
            for card in cards[:20]:
                title_el = card.query_selector("[data-qa='posting-name'], h2, h3")
                company_el = card.query_selector("[data-qa='posting-company-name'], .company")
                link_el = card.query_selector("a[href]")
                if not title_el or not link_el:
                    continue
                href = link_el.get_attribute("href") or ""
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                ext_id = re.sub(r"[^a-zA-Z0-9]", "", href)[-20:]
                jobs.append({
                    "source": "Bumeran",
                    "external_id": ext_id,
                    "title": title_el.inner_text().strip(),
                    "company": company_el.inner_text().strip() if company_el else "Empresa desconocida",
                    "location": "Venezuela",
                    "job_type": "Presencial/Híbrido",
                    "salary": "",
                    "description": "",
                    "url": full_url,
                    "tags": [keywords.split()[0]],
                })
            browser.close()
            return jobs
    except Exception as e:
        print(f"[Bumeran/Playwright] {e}")
        return []
