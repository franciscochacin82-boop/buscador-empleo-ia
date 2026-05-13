"""
We Work Remotely RSS feed — curated remote jobs.
"""
import xml.etree.ElementTree as ET
import requests
import re

RSS_URLS = [
    "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
    "https://weworkremotely.com/categories/remote-copywriting-jobs.rss",
    "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
]


def search() -> list[dict]:
    results = []
    seen = set()
    for url in RSS_URLS:
        results += _fetch_rss(url, seen)
    return results


def _fetch_rss(url: str, seen: set) -> list[dict]:
    try:
        headers = {"User-Agent": "JobFinderApp/1.0 (personal use)"}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        jobs = []
        for item in items:
            title_raw = _text(item, "title") or ""
            # Format: "Company: Position at Company"
            parts = title_raw.split(": ", 1)
            company = parts[0].strip() if len(parts) > 1 else "Empresa desconocida"
            position = parts[1].strip() if len(parts) > 1 else title_raw.strip()

            link = _text(item, "link") or ""
            ext_id = link.split("/")[-1] or title_raw[:40]

            if ext_id in seen:
                continue
            seen.add(ext_id)

            desc_raw = _text(item, "description") or ""
            desc_clean = re.sub(r"<[^>]+>", " ", desc_raw).strip()

            region = _text(item, "{https://weworkremotely.com}region") or "Worldwide"

            jobs.append({
                "source": "We Work Remotely",
                "external_id": ext_id,
                "title": position,
                "company": company,
                "location": f"Remoto ({region})",
                "job_type": "Remoto",
                "salary": "",
                "description": desc_clean[:2000],
                "url": link,
                "tags": [],
            })
        return jobs
    except Exception as e:
        print(f"[WWR] Error {url}: {e}")
        return []


def _text(el, tag: str) -> str | None:
    child = el.find(tag)
    return child.text if child is not None else None
