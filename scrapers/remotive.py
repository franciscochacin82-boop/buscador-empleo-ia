"""
Remotive public API — curated remote jobs, strong in marketing/content/design.
https://remotive.com/api/remote-jobs
"""
import re
import requests

API_URL = "https://remotive.com/api/remote-jobs"

def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def search(keywords: str = "marketing", limit: int = 50) -> list[dict]:
    try:
        resp = requests.get(
            API_URL,
            params={"search": keywords, "limit": limit},
            timeout=15,
        )
        resp.raise_for_status()
        jobs = []
        for j in resp.json().get("jobs", []):
            jobs.append({
                "source": "Remotive",
                "external_id": str(j.get("id", "")),
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "100% Remoto") or "100% Remoto",
                "job_type": "Remoto",
                "salary": j.get("salary", ""),
                "description": _clean(j.get("description", "")),
                "url": j.get("url", ""),
                "tags": j.get("tags", []),
            })
        return jobs
    except Exception as e:
        print(f"[Remotive] Error: {e}")
        return []
