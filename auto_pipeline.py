"""
Full auto-apply pipeline:
  1. Search all job boards
  2. Generate AI cover letter for each job
  3. Scrape job page to extract contact email
  4. If email found  → send application email with PDF attached
  5. If no email     → attempt web apply via Playwright (Torre.co / Computrabajo)
  6. Return detailed results log
"""
import re
import time
from typing import Callable

import requests
from bs4 import BeautifulSoup

import database as db
import cover_letter as cl
import document_generator as dg
import email_sender as es
from scrapers import (
    torre, remoteok, wwr, computrabajo,
    remotive, workingnomads, bumeran, opcionempleo, indeed, glassdoor,
)

EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)
# Emails to ignore (generic/platform addresses)
EMAIL_BLACKLIST = {
    "noreply", "no-reply", "donotreply", "example.com", "test@",
    "support@", "@computrabajo", "@torre.ai", "@remoteok", "@weworkremotely",
    "png", "jpg", "gif", "svg",
}


def run(
    profile: dict,
    smtp_email: str = "",
    smtp_pass: str = "",
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 587,
    keywords: str = "marketing comunicaciones",
    torre_creds: dict = None,
    computrabajo_creds: dict = None,
    on_progress: Callable[[str], None] = None,
    only_new: bool = True,
) -> list[dict]:
    """
    Run the complete pipeline. Returns a list of result dicts.

    torre_creds / computrabajo_creds: {"email": ..., "password": ...}
    only_new: skip jobs already marked applied/interview/offer
    """

    def log(msg: str):
        if on_progress:
            on_progress(msg)

    smtp_ready = bool(smtp_email and smtp_pass)

    # ── Step 1: Search all boards ─────────────────────────────────────────
    SCRAPERS = [
        ("Torre.co",           lambda: torre.search(keywords=keywords)),
        ("Remote OK",          lambda: remoteok.search(keywords=keywords)),
        ("We Work Remotely",   lambda: wwr.search()),
        ("Computrabajo VE",    lambda: computrabajo.search()),
        ("Remotive",           lambda: remotive.search(keywords=keywords)),
        ("Working Nomads",     lambda: workingnomads.search(keywords=keywords)),
        ("Bumeran VE",         lambda: bumeran.search(keywords=keywords)),
        ("OpcionEmpleo VE",    lambda: opcionempleo.search(keywords=keywords)),
        ("Indeed",             lambda: indeed.search(keywords=keywords)),
        ("Glassdoor",          lambda: glassdoor.search(keywords=keywords)),
    ]
    for name, fn in SCRAPERS:
        log(f"🔍 Buscando en {name}…")
        try:
            db.upsert_jobs(fn())
        except Exception as e:
            log(f"  ⚠️ {name} falló: {e}")

    all_jobs = db.get_jobs()
    if only_new:
        pending = [j for j in all_jobs
                   if j.get("status") not in ("applied", "interview", "offer")]
    else:
        pending = all_jobs

    log(f"📋 {len(pending)} vacantes para procesar")

    results: list[dict] = []

    for i, job in enumerate(pending, 1):
        log(f"[{i}/{len(pending)}] {job['title']} — {job['company']}")

        # ── Step 2: Generate cover letter ─────────────────────────────────
        existing = db.get_application(job["id"])
        letter = (existing or {}).get("cover_letter") or ""
        if not letter:
            try:
                letter = cl.generate(profile, job)
                db.save_application(job["id"], "saved", letter)
                log("  ✍️  Carta generada con IA")
            except Exception as exc:
                letter = ""
                log(f"  ⚠️  IA no disponible ({exc}) — se enviará mensaje genérico")

        # ── Step 3: Find contact email ─────────────────────────────────────
        contact_email = _find_email(job)

        result = {
            "job_id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "source": job["source"],
            "url": job.get("url", ""),
            "contact_email": contact_email or "",
            "method": "",
            "success": False,
            "message": "",
        }

        # ── Step 4a: Apply by email ────────────────────────────────────────
        if contact_email and smtp_ready:
            log(f"  📧 Email: {contact_email} — enviando…")
            pdf = dg.to_pdf(profile, job, letter or es.build_body(profile, job))
            safe_name = profile.get("name", "Candidata").replace(" ", "_")
            ok, msg = es.send_application(
                smtp_email=smtp_email,
                smtp_password=smtp_pass,
                to_email=contact_email,
                subject=es.build_subject(profile, job),
                body=es.build_body(profile, job),
                attachment=pdf,
                attachment_name=f"CV_{safe_name}.pdf",
                smtp_host=smtp_host,
                smtp_port=smtp_port,
            )
            result.update(method="email", success=ok, message=msg)
            if ok:
                db.save_application(job["id"], "applied", letter)
                log("  ✅ Enviado")
            else:
                log(f"  ❌ {msg}")

        # ── Step 4b: Web apply (Playwright) ───────────────────────────────
        elif not contact_email:
            applied_web = False
            source = job.get("source", "")

            if source == "Torre.co" and torre_creds:
                log("  🌐 Aplicando en Torre.co…")
                try:
                    from web_apply import apply_torre
                    ok, msg = apply_torre(job["url"], torre_creds["email"], torre_creds["password"])
                    result.update(method="torre_web", success=ok, message=msg)
                    if ok:
                        db.save_application(job["id"], "applied", letter)
                        log(f"  ✅ {msg}")
                    else:
                        log(f"  ❌ {msg}")
                    applied_web = True
                except ImportError:
                    log("  ⚠️  Playwright no instalado — omitiendo web apply")

            elif source == "Computrabajo" and computrabajo_creds:
                log("  🌐 Aplicando en Computrabajo…")
                try:
                    from web_apply import apply_computrabajo
                    ok, msg = apply_computrabajo(
                        job["url"],
                        computrabajo_creds["email"],
                        computrabajo_creds["password"],
                    )
                    result.update(method="computrabajo_web", success=ok, message=msg)
                    if ok:
                        db.save_application(job["id"], "applied", letter)
                        log(f"  ✅ {msg}")
                    else:
                        log(f"  ❌ {msg}")
                    applied_web = True
                except ImportError:
                    log("  ⚠️  Playwright no instalado — omitiendo web apply")

            if not applied_web:
                result.update(
                    method="manual_needed",
                    success=False,
                    message="Sin email — aplica en: " + job.get("url", ""),
                )
                log("  ℹ️  Sin email de contacto — requiere aplicación manual")

        else:
            # Has email but no SMTP configured
            result.update(
                method="email_not_configured",
                success=False,
                message=f"Email encontrado ({contact_email}) pero SMTP no configurado",
            )
            log(f"  ⚠️  Email {contact_email} encontrado — configura SMTP para enviar")

        results.append(result)
        time.sleep(0.5)  # polite delay

    applied = sum(1 for r in results if r["success"])
    manual = sum(1 for r in results if r["method"] == "manual_needed")
    emails_found = sum(1 for r in results if r["contact_email"])
    log(
        f"\n🎯 Finalizado: {applied} aplicaciones enviadas, "
        f"{emails_found} emails encontrados, "
        f"{manual} requieren atención manual"
    )
    return results


# ── Email extraction ──────────────────────────────────────────────────────────

def _find_email(job: dict) -> str | None:
    """Check description, then scrape job page for a contact email."""
    # 1. Check description field
    email = _extract(job.get("description") or "")
    if email:
        return email

    # 2. Fetch the actual job page
    url = job.get("url", "")
    if not url:
        return None
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "head"]):
            tag.decompose()
        return _extract(soup.get_text(" ", strip=True))
    except Exception:
        return None


def _extract(text: str) -> str | None:
    for m in EMAIL_RE.finditer(text):
        email = m.group(0).lower()
        if not any(b in email for b in EMAIL_BLACKLIST):
            return m.group(0)
    return None
