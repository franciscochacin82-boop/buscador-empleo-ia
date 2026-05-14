"""
Playwright-based web apply for Torre.co, Computrabajo, Indeed, and Glassdoor.
Requires: pip install playwright && playwright install chromium
"""
import os
import re
import time
import tempfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def is_available() -> bool:
    return PLAYWRIGHT_AVAILABLE


def _check():
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError(
            "Playwright no está instalado. Ejecuta:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )


def _browser_context(playwright, headless: bool = True):
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    # Hide automation signals
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, ctx


# ── Indeed ────────────────────────────────────────────────────────────────────

def search_and_apply_indeed(
    email: str,
    password: str,
    keywords: str,
    profile: dict,
    max_jobs: int = 25,
) -> list[dict]:
    """
    Login to Indeed, search for jobs, apply to every Easy Apply listing.
    Returns a list of result dicts: {title, company, url, success, message}.
    """
    _check()
    results = []

    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        try:
            # ── Login ──────────────────────────────────────────────────────
            ok, msg = _indeed_login(page, email, password)
            if not ok:
                return [{"title": "Indeed login", "company": "", "url": "https://indeed.com",
                         "success": False, "message": msg}]

            # ── Search ─────────────────────────────────────────────────────
            page.goto(
                f"https://www.indeed.com/jobs?q={keywords}&sort=date&fromage=14",
                timeout=25000,
            )
            page.wait_for_load_state("networkidle", timeout=15000)

            # Collect job links from search results
            job_links = _extract_indeed_jobs(page, max_jobs)
            if not job_links:
                return [{"title": "Indeed search", "company": "", "url": "",
                         "success": False, "message": "No se encontraron vacantes en Indeed"}]

            # ── Apply to each job ──────────────────────────────────────────
            for job_url, title, company in job_links:
                try:
                    page.goto(job_url, timeout=20000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(1.5)

                    ok, msg = _indeed_easy_apply(page, profile)
                    results.append({
                        "title": title,
                        "company": company,
                        "url": job_url,
                        "success": ok,
                        "message": msg,
                    })
                except Exception as e:
                    results.append({
                        "title": title, "company": company,
                        "url": job_url, "success": False, "message": str(e),
                    })
                time.sleep(1)

        finally:
            browser.close()

    return results


def _indeed_login(page, email: str, password: str) -> tuple[bool, str]:
    try:
        page.goto("https://secure.indeed.com/account/login", timeout=20000)
        page.wait_for_load_state("domcontentloaded")

        # Email step
        email_sel = 'input[type="email"], input[name="__email"], input[id*="email"]'
        page.wait_for_selector(email_sel, timeout=10000)
        page.fill(email_sel, email)
        page.click('button[type="submit"]')
        time.sleep(2)

        # Password step (may be on same page or next page)
        pw_sel = 'input[type="password"]'
        try:
            page.wait_for_selector(pw_sel, timeout=8000)
            page.fill(pw_sel, password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass  # Password might already have been processed

        url = page.url
        if "captcha" in url or "challenge" in url:
            return False, (
                "⚠️ Indeed pide verificación de seguridad. "
                "Inicia sesión manualmente una vez en indeed.com para establecer la sesión, "
                "luego vuelve a intentarlo."
            )
        if "login" in url:
            return False, "❌ Login de Indeed falló — verifica email y contraseña"

        return True, "Sesión iniciada en Indeed"
    except Exception as e:
        return False, f"❌ Error al iniciar sesión en Indeed: {e}"


def _extract_indeed_jobs(page, max_jobs: int) -> list[tuple[str, str, str]]:
    """Return list of (url, title, company) from search results."""
    jobs = []
    try:
        cards = page.locator("li.css-1ac2h1w, .job_seen_beacon, li[data-jk]").all()[:max_jobs]
        for card in cards:
            try:
                link_el = card.locator("a[href*='/rc/clk'], a[href*='/pagead'], h2 a").first
                title_el = card.locator("h2 span[title], h2 a span, .jobTitle span").first
                company_el = card.locator("[data-testid='company-name'], .companyName, .css-63koeb").first

                href = link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://www.indeed.com" + href

                title = ""
                try:
                    title = title_el.inner_text(timeout=2000).strip()
                except Exception:
                    pass

                company = ""
                try:
                    company = company_el.inner_text(timeout=2000).strip()
                except Exception:
                    pass

                if href and title:
                    jobs.append((href, title, company))
            except Exception:
                continue
    except Exception as e:
        print(f"[Indeed] extract jobs error: {e}")
    return jobs


def _indeed_easy_apply(page, profile: dict) -> tuple[bool, str]:
    """Click Easy Apply and fill the multi-step form."""
    # Find the apply button
    apply_sel = (
        "button.indeedApplyButton, "
        "button[data-testid='indeedApplyButton'], "
        ".ia-IndeedApplyButton, "
        "button:has-text('Apply now'), "
        "button:has-text('Easy Apply')"
    )
    try:
        btn = page.locator(apply_sel).first
        if not btn.is_visible(timeout=5000):
            return False, "Sin botón Easy Apply en esta vacante"
        btn.click()
        time.sleep(2)
    except PWTimeout:
        return False, "Sin botón Easy Apply en esta vacante"

    # Generate a resume file to upload if asked
    resume_path = _make_resume_file(profile)

    # Multi-step form — up to 10 steps
    for step in range(10):
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1)

        _fill_indeed_step(page, profile, resume_path)

        # Submit?
        submit = page.locator(
            "button:has-text('Submit your application'), "
            "button:has-text('Submit application'), "
            "button:has-text('Enviar solicitud')"
        ).first
        try:
            if submit.is_visible(timeout=2000):
                submit.click()
                time.sleep(2)
                return True, "✅ Aplicación enviada en Indeed"
        except PWTimeout:
            pass

        # Next step
        next_btn = page.locator(
            "button:has-text('Continue'), "
            "button:has-text('Next'), "
            "button[aria-label*='Continue']"
        ).first
        try:
            if next_btn.is_visible(timeout=2000):
                next_btn.click()
                time.sleep(1.5)
                continue
        except PWTimeout:
            pass

        break

    return False, "No se pudo completar el formulario de Indeed"


def _fill_indeed_step(page, profile: dict, resume_path: str | None):
    """Fill whatever fields are visible on the current step."""
    # Phone
    for sel in ['input[name="phone"]', 'input[type="tel"]', 'input[autocomplete="tel"]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000) and not el.input_value():
                el.fill(profile.get("phone", ""))
        except Exception:
            pass

    # City / Location
    for sel in ['input[name="city"]', 'input[placeholder*="city" i]', 'input[placeholder*="location" i]']:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1000) and not el.input_value():
                el.fill(profile.get("location", "Caracas, Venezuela"))
        except Exception:
            pass

    # Resume upload
    if resume_path:
        for sel in ['input[type="file"]', 'input[accept*="pdf"]', 'input[accept*="doc"]']:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.set_input_files(resume_path)
            except Exception:
                pass

    # Radio buttons — default "Yes" for positive options
    try:
        radios = page.locator('input[type="radio"]').all()
        for radio in radios:
            val = (radio.get_attribute("value") or "").lower()
            if val in ("yes", "true", "1", "authorized"):
                radio.check()
    except Exception:
        pass

    # Select dropdowns (e.g. years of experience)
    try:
        selects = page.locator("select:visible").all()
        for sel_el in selects:
            opts = sel_el.locator("option").all()
            if len(opts) > 1:
                # Pick the last non-empty option (usually highest experience)
                for opt in reversed(opts):
                    val = opt.get_attribute("value") or ""
                    if val and val != "0":
                        sel_el.select_option(val)
                        break
    except Exception:
        pass

    # Text areas (cover letter / summary boxes)
    try:
        textareas = page.locator("textarea:visible").all()
        for ta in textareas:
            if not ta.input_value():
                ta.fill(profile.get("summary", "")[:1000])
    except Exception:
        pass


def _make_resume_file(profile: dict) -> str | None:
    """Generate a plain-text resume file for upload."""
    try:
        lines = [
            profile.get("name", ""),
            profile.get("email", "") + "  |  " + profile.get("phone", ""),
            profile.get("location", ""),
            profile.get("linkedin", ""),
            "",
            "RESUMEN PROFESIONAL",
            profile.get("summary", ""),
            "",
            "EXPERIENCIA",
            profile.get("experience", ""),
            "",
            "HABILIDADES",
            profile.get("skills", ""),
            "",
            "EDUCACIÓN",
            profile.get("education", ""),
            "",
            "IDIOMAS",
            profile.get("languages", ""),
        ]
        text = "\n".join(line for line in lines if line is not None)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        return tmp.name
    except Exception:
        return None


# ── Glassdoor ─────────────────────────────────────────────────────────────────

def search_and_apply_glassdoor(
    email: str,
    password: str,
    keywords: str,
    profile: dict,
    max_jobs: int = 25,
) -> list[dict]:
    """
    Login to Glassdoor, search for jobs, apply to Easy Apply listings.
    """
    _check()
    results = []

    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        try:
            ok, msg = _glassdoor_login(page, email, password)
            if not ok:
                return [{"title": "Glassdoor login", "company": "", "url": "https://glassdoor.com",
                         "success": False, "message": msg}]

            # Search
            page.goto(
                f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keywords}&fromAge=14",
                timeout=25000,
            )
            page.wait_for_load_state("networkidle", timeout=15000)

            # Collect jobs
            job_links = _extract_glassdoor_jobs(page, max_jobs)
            if not job_links:
                return [{"title": "Glassdoor search", "company": "", "url": "",
                         "success": False, "message": "No se encontraron vacantes en Glassdoor"}]

            resume_path = _make_resume_file(profile)

            for job_url, title, company in job_links:
                try:
                    page.goto(job_url, timeout=20000)
                    page.wait_for_load_state("domcontentloaded")
                    time.sleep(2)

                    ok, msg = _glassdoor_easy_apply(page, profile, resume_path)
                    results.append({
                        "title": title, "company": company,
                        "url": job_url, "success": ok, "message": msg,
                    })
                except Exception as e:
                    results.append({
                        "title": title, "company": company,
                        "url": job_url, "success": False, "message": str(e),
                    })
                time.sleep(1.5)

        finally:
            browser.close()

    return results


def _glassdoor_login(page, email: str, password: str) -> tuple[bool, str]:
    try:
        page.goto("https://www.glassdoor.com/profile/login_input.htm", timeout=20000)
        page.wait_for_load_state("domcontentloaded")

        page.fill('input[name="username"], input[type="email"]', email)
        page.fill('input[name="password"], input[type="password"]', password)
        page.click('button[type="submit"], button:has-text("Sign In")')
        page.wait_for_load_state("networkidle", timeout=15000)

        url = page.url
        if "login" in url and "error" in page.content().lower():
            return False, "❌ Login de Glassdoor falló — verifica email y contraseña"
        if "captcha" in url or "challenge" in url.lower():
            return False, "⚠️ Glassdoor pide verificación. Inicia sesión manualmente una vez."

        return True, "Sesión iniciada en Glassdoor"
    except Exception as e:
        return False, f"❌ Error al iniciar sesión en Glassdoor: {e}"


def _extract_glassdoor_jobs(page, max_jobs: int) -> list[tuple[str, str, str]]:
    jobs = []
    try:
        cards = page.locator("li.react-job-listing, article[data-id], [data-test='jobListing']").all()[:max_jobs]
        for card in cards:
            try:
                link_el = card.locator("a").first
                title_el = card.locator("[data-test='job-title'], h3, h2").first

                href = link_el.get_attribute("href") or ""
                if href and not href.startswith("http"):
                    href = "https://www.glassdoor.com" + href

                title = title_el.inner_text(timeout=2000).strip() if title_el else ""
                company_el = card.locator("[data-test='employer-name'], .EmployerProfile_compactEmployerName__9MGcV").first
                company = company_el.inner_text(timeout=2000).strip() if company_el.is_visible(timeout=1000) else ""

                if href and title:
                    jobs.append((href, title, company))
            except Exception:
                continue
    except Exception as e:
        print(f"[Glassdoor] extract error: {e}")
    return jobs


def _glassdoor_easy_apply(page, profile: dict, resume_path: str | None) -> tuple[bool, str]:
    # Look for Easy Apply button
    apply_sel = (
        "button[data-test='applyButton'], "
        "button:has-text('Easy Apply'), "
        "button:has-text('Apply Now'), "
        "[class*='EasyApply'], "
        "button[aria-label*='Apply']"
    )
    try:
        btn = page.locator(apply_sel).first
        if not btn.is_visible(timeout=5000):
            return False, "Sin botón Easy Apply en Glassdoor"
        btn.click()
        time.sleep(2)
    except PWTimeout:
        return False, "Sin botón Easy Apply en Glassdoor"

    # Handle modal / redirect
    for step in range(8):
        page.wait_for_load_state("domcontentloaded")
        time.sleep(1.5)

        # Fill fields (same helper works)
        _fill_indeed_step(page, profile, resume_path)

        # Submit
        submit = page.locator(
            "button:has-text('Submit'), button:has-text('Apply'), "
            "button:has-text('Send application')"
        ).first
        try:
            if submit.is_visible(timeout=2000):
                submit.click()
                time.sleep(2)
                return True, "✅ Aplicación enviada en Glassdoor"
        except PWTimeout:
            pass

        # Next
        next_btn = page.locator(
            "button:has-text('Next'), button:has-text('Continue')"
        ).first
        try:
            if next_btn.is_visible(timeout=2000):
                next_btn.click()
                time.sleep(1.5)
                continue
        except PWTimeout:
            pass

        break

    return False, "No se pudo completar el formulario de Glassdoor"


# ── Per-job wrappers (used by auto_pipeline for individual jobs) ──────────────

def apply_indeed_job(job_url: str, email: str, password: str, profile: dict = None) -> tuple[bool, str]:
    """Apply to a single Indeed job URL. Logs in fresh each call (slow but simple)."""
    _check()
    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        try:
            ok, msg = _indeed_login(page, email, password)
            if not ok:
                return False, msg
            page.goto(job_url, timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(1.5)
            return _indeed_easy_apply(page, profile or {})
        finally:
            browser.close()


def apply_glassdoor_job(job_url: str, email: str, password: str, profile: dict = None) -> tuple[bool, str]:
    """Apply to a single Glassdoor job URL."""
    _check()
    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        try:
            ok, msg = _glassdoor_login(page, email, password)
            if not ok:
                return False, msg
            page.goto(job_url, timeout=20000)
            page.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            resume_path = _make_resume_file(profile or {})
            return _glassdoor_easy_apply(page, profile or {}, resume_path)
        finally:
            browser.close()


# ── Torre.co ──────────────────────────────────────────────────────────────────

def apply_torre(job_url: str, email: str, password: str) -> tuple[bool, str]:
    _check()
    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        try:
            page.goto("https://torre.ai/login", timeout=25000)
            page.wait_for_selector('input[type="email"]', timeout=12000)
            page.fill('input[type="email"]', email)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"]')
            try:
                page.wait_for_url("**/opportunities**", timeout=12000)
            except PWTimeout:
                page.wait_for_load_state("networkidle", timeout=10000)

            if "login" in page.url:
                return False, "Login fallido — verifica credenciales de Torre.co"

            page.goto(job_url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)

            apply_sel = (
                'button:has-text("Apply now"), button:has-text("Apply"), '
                'button:has-text("Aplicar"), a:has-text("Apply now")'
            )
            try:
                page.locator(apply_sel).first.click(timeout=8000)
            except PWTimeout:
                return False, "No se encontró el botón Apply en Torre.co"

            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)

            confirm_sel = (
                'button:has-text("Send application"), button:has-text("Submit"), '
                'button:has-text("Confirm"), button[type="submit"]'
            )
            try:
                btn = page.locator(confirm_sel).first
                if btn.is_visible(timeout=4000):
                    btn.click()
                    time.sleep(2)
            except PWTimeout:
                pass

            return True, "✅ Postulación enviada en Torre.co"
        except PWTimeout:
            return False, "⏱️ Tiempo de espera agotado en Torre.co"
        except Exception as exc:
            return False, f"❌ Error Torre.co: {exc}"
        finally:
            browser.close()


# ── Computrabajo ──────────────────────────────────────────────────────────────

def apply_computrabajo(job_url: str, email: str, password: str) -> tuple[bool, str]:
    _check()
    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        try:
            page.goto("https://www.computrabajo.com.ve/login", timeout=20000)
            page.wait_for_selector(
                'input[name="email"], input[type="email"], #email', timeout=12000
            )
            page.fill('input[name="email"], input[type="email"], #email', email)
            page.fill('input[name="password"], input[type="password"], #password', password)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=15000)

            if "login" in page.url:
                return False, "Login fallido — verifica credenciales de Computrabajo"

            page.goto(job_url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)

            btn_sel = (
                'a:has-text("Postularme"), button:has-text("Postularme"), '
                'a:has-text("Aplicar"), .btn_postular, #btn_postular'
            )
            try:
                page.locator(btn_sel).first.click(timeout=8000)
            except PWTimeout:
                return False, "No se encontró el botón Postularme en Computrabajo"

            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)

            confirm_sel = (
                'button:has-text("Confirmar"), button:has-text("Enviar"), '
                'button:has-text("Aceptar"), button[type="submit"]'
            )
            try:
                btn = page.locator(confirm_sel).first
                if btn.is_visible(timeout=4000):
                    btn.click()
                    time.sleep(2)
            except PWTimeout:
                pass

            return True, "✅ Postulación enviada en Computrabajo"
        except PWTimeout:
            return False, "⏱️ Tiempo de espera agotado en Computrabajo"
        except Exception as exc:
            return False, f"❌ Error Computrabajo: {exc}"
        finally:
            browser.close()
