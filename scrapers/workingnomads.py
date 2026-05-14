"""
Working Nomads public JSON API — remote jobs worldwide.
https://www.workingnomads.com/api/exposed_jobs/
"""
import re
import requests

API_URL = "https://www.workingnomads.com/api/exposed_jobs/"

def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def search(keywords: str = "marketing") -> list[dict]:
    try:
        resp = requests.get(
            API_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        all_jobs = resp.json()

        kw_list = [k.lower().strip() for k in keywords.replace(",", " ").split() if k.strip()]
        jobs = []
        for j in all_jobs:
            title = j.get("title", "").lower()
            tags = " ".join(j.get("tags", [])).lower()
            desc = j.get("description", "").lower()
            if not any(k in title or k in tags or k in desc for k in kw_list):
                continue
            jobs.append({
                "source": "Working Nomads",
                "external_id": str(j.get("id", "")),
                "title": j.get("title", ""),
                "company": j.get("company", ""),
                "location": "Remoto (Worldwide)",
                "job_type": "Remoto",
                "salary": "",
                "description": _clean(j.get("description", "")),
                "url": j.get("url", ""),
                "tags": j.get("tags", []),
            })
        return jobs
    except Exception as e:
        print(f"[WorkingNomads] Error: {e}")
        return []
