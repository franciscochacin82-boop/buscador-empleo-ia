"""
Torre.co public API — best job board for Latin America.
Docs: https://torre.ai/api/
"""
import requests

SEARCH_URL = "https://torre.ai/api/opportunities/_search"


def search(keywords: str = "marketing comunicaciones", location: str = "Venezuela", limit: int = 40) -> list[dict]:
    payload = {
        "query": keywords,
        "filters": {},
        "offset": 0,
        "size": limit,
        "aggregate": False,
        "lang": "es",
    }
    # Also try remote
    results = _fetch(payload)

    # Second pass: remote only
    remote_payload = {**payload, "filters": {"remote": True}, "query": keywords}
    remote_payload.pop("lang", None)
    results += _fetch(remote_payload)

    seen = set()
    unique = []
    for r in results:
        if r["external_id"] not in seen:
            seen.add(r["external_id"])
            unique.append(r)
    return unique


def _fetch(payload: dict) -> list[dict]:
    try:
        resp = requests.post(SEARCH_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        jobs = []
        for item in data.get("results", []):
            opp = item.get("opportunity", item)
            locations = opp.get("locations", [])
            loc_str = ", ".join(
                f"{l.get('city', '')} {l.get('country', '')}".strip() for l in locations
            ) or ("Remoto" if opp.get("remote") else "No especificado")

            jobs.append({
                "source": "Torre.co",
                "external_id": str(opp.get("id", opp.get("publicId", ""))),
                "title": opp.get("objective", "Sin título"),
                "company": (opp.get("organizations") or [{}])[0].get("name", "Empresa desconocida"),
                "location": loc_str,
                "job_type": "Remoto" if opp.get("remote") else opp.get("type", ""),
                "salary": _salary(opp),
                "description": opp.get("details", ""),
                "url": f"https://torre.ai/jobs/{opp.get('publicId', opp.get('id', ''))}",
                "tags": [s.get("name", "") for s in opp.get("skills", [])],
            })
        return jobs
    except Exception as e:
        print(f"[Torre] Error: {e}")
        return []


def _salary(opp: dict) -> str:
    comp = opp.get("compensation", {})
    if not comp:
        return ""
    mn = comp.get("minAmount", "")
    mx = comp.get("maxAmount", "")
    currency = comp.get("currency", "USD")
    if mn and mx:
        return f"{currency} {mn:,} – {mx:,}"
    if mn:
        return f"{currency} {mn:,}+"
    return ""
