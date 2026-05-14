"""
Indeed RSS feed scraper — returns recent job postings.
Indeed aggressively blocks bots; this uses their RSS endpoint which is more lenient.
"""
import re
import xml.etree.ElementTree as ET
import requests

RSS_URL = "https://www.indeed.com/rss"

def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def search(keywords: str = "marketing", location: str = "", limit: int = 25) -> list[dict]:
    # Try main site then Venezuela-specific domain
    for base in ["https://www.indeed.com/rss", "https://ve.indeed.com/rss"]:
        for loc in [location, "remote", ""]:
            jobs = _fetch(keywords, loc, limit, rss_base=base)
            if jobs:
                return jobs
    return []


def _fetch(keywords: str, location: str, limit: int, rss_base: str = RSS_URL) -> list[dict]:
    try:
        params = {"q": keywords, "sort": "date", "limit": limit}
        if location:
            params["l"] = location
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        }
        resp = requests.get(rss_base, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        jobs = []
        for item in items:
            title_raw = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc_raw = item.findtext("description") or ""

            # Indeed format: "Job Title - Company Name - Location"
            parts = title_raw.split(" - ")
            job_title = parts[0].strip() if parts else title_raw
            company = parts[1].strip() if len(parts) > 1 else "Empresa desconocida"
            loc_str = parts[2].strip() if len(parts) > 2 else (location or "Remoto")

            ext_id = ""
            if "jk=" in link:
                ext_id = link.split("jk=")[1][:20]
            else:
                ext_id = link[-30:]

            jobs.append({
                "source": "Indeed",
                "external_id": ext_id,
                "title": job_title,
                "company": company,
                "location": loc_str,
                "job_type": "",
                "salary": "",
                "description": _clean(desc_raw)[:1500],
                "url": link,
                "tags": [],
            })
        return jobs
    except Exception as e:
        print(f"[Indeed] Error: {e}")
        return []
