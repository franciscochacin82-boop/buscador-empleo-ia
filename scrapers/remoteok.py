"""
Remote OK public JSON API — remote jobs worldwide, good USD salaries.
"""
import re
import requests

def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()

API_URL = "https://remoteok.com/api"
COMM_TAGS = {"marketing", "communications", "content", "social-media", "pr",
             "copywriting", "seo", "growth", "brand", "digital-marketing",
             "community", "media", "writing", "ux-writing"}


def search(keywords: str = "marketing") -> list[dict]:
    try:
        headers = {"User-Agent": "JobFinderApp/1.0 (personal use)"}
        resp = requests.get(API_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # First element is metadata
        jobs_raw = [j for j in data if isinstance(j, dict) and j.get("id")]

        kw_lower = keywords.lower().split()
        results = []
        for job in jobs_raw:
            tags = [t.lower() for t in job.get("tags", [])]
            title = job.get("position", "").lower()
            desc = job.get("description", "").lower()

            # relevance filter
            match = (
                any(t in COMM_TAGS for t in tags)
                or any(k in title for k in kw_lower)
                or any(k in " ".join(tags) for k in kw_lower)
            )
            if not match:
                continue

            salary = ""
            if job.get("salary_min") and job.get("salary_max"):
                salary = f"USD {int(job['salary_min']):,} – {int(job['salary_max']):,}/yr"

            results.append({
                "source": "Remote OK",
                "external_id": str(job["id"]),
                "title": job.get("position", "Sin título"),
                "company": job.get("company", "Empresa desconocida"),
                "location": "100% Remoto",
                "job_type": "Remoto",
                "salary": salary,
                "description": _clean(job.get("description", "")),
                "url": job.get("url", f"https://remoteok.com/remote-jobs/{job['id']}"),
                "tags": job.get("tags", []),
            })
        return results
    except Exception as e:
        print(f"[RemoteOK] Error: {e}")
        return []
