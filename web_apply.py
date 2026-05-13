"""
Playwright-based web apply for Torre.co and Computrabajo Venezuela.
Requires: pip install playwright && playwright install chromium
"""
import time

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _check():
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError(
            "Playwright no está instalado. Ejecuta:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )


# ── Torre.co ──────────────────────────────────────────────────────────────────

def apply_torre(job_url: str, email: str, password: str) -> tuple[bool, str]:
    """
    Log into Torre.co and apply to a job.
    Returns (success, message).
    """
    _check()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = ctx.new_page()
        try:
            # ── Login ────────────────────────────────────────────────────
            page.goto("https://torre.ai/login", timeout=25000)
            page.wait_for_selector('input[type="email"]', timeout=12000)
            page.fill('input[type="email"]', email)
            page.fill('input[type="password"]', password)
            page.click('button[type="submit"]')
            try:
                page.wait_for_url("**/opportunities**", timeout=12000)
            except PWTimeout:
                # Try alternative post-login URL patterns
                page.wait_for_load_state("networkidle", timeout=10000)

            if "login" in page.url:
                return False, "Login fallido — verifica credenciales de Torre.co"

            # ── Navigate to job ──────────────────────────────────────────
            page.goto(job_url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # ── Click Apply ──────────────────────────────────────────────
            apply_sel = (
                'button:has-text("Apply now"), '
                'button:has-text("Apply"), '
                'button:has-text("Aplicar"), '
                'a:has-text("Apply now"), '
                'a:has-text("Apply")'
            )
            try:
                page.locator(apply_sel).first.click(timeout=8000)
            except PWTimeout:
                return False, "No se encontró el botón Apply en Torre.co"

            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)

            # ── Confirm / submit if modal appeared ───────────────────────
            confirm_sel = (
                'button:has-text("Send application"), '
                'button:has-text("Submit"), '
                'button:has-text("Confirm"), '
                'button[type="submit"]'
            )
            try:
                btn = page.locator(confirm_sel).first
                if btn.is_visible(timeout=4000):
                    btn.click()
                    time.sleep(2)
            except PWTimeout:
                pass  # no confirmation dialog — single-click apply succeeded

            return True, "✅ Postulación enviada en Torre.co"

        except PWTimeout:
            return False, "⏱️ Tiempo de espera agotado en Torre.co"
        except Exception as exc:
            return False, f"❌ Error Torre.co: {exc}"
        finally:
            browser.close()


def register_torre(name: str, email: str, password: str) -> tuple[bool, str]:
    """
    Create a new Torre.co account.
    NOTE: After registration, Torre sends a verification email.
    Returns (success, message) — success means form submitted, not verified.
    """
    _check()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible so user can verify email
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            page.goto("https://torre.ai/register", timeout=20000)
            page.wait_for_selector('input[name="name"], input[placeholder*="name"]', timeout=10000)

            page.fill('input[name="name"], input[placeholder*="name"]', name)
            page.fill('input[type="email"]', email)
            page.fill('input[type="password"]', password)

            page.click('button[type="submit"]')
            time.sleep(3)

            if "verify" in page.url or "confirm" in page.url:
                return True, (
                    "Cuenta creada. Revisa tu correo y haz clic en el enlace "
                    "de verificación antes de continuar."
                )
            return True, "Registro enviado en Torre.co"
        except Exception as exc:
            return False, f"Error al registrar en Torre.co: {exc}"
        finally:
            # Keep browser open briefly so user can see
            time.sleep(3)
            browser.close()


# ── Computrabajo Venezuela ────────────────────────────────────────────────────

def apply_computrabajo(job_url: str, email: str, password: str) -> tuple[bool, str]:
    """
    Log into Computrabajo and click Postularme on a job.
    """
    _check()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = ctx.new_page()
        try:
            # ── Login ────────────────────────────────────────────────────
            page.goto("https://www.computrabajo.com.ve/login", timeout=20000)
            page.wait_for_selector(
                'input[name="email"], input[type="email"], #email',
                timeout=12000,
            )
            page.fill('input[name="email"], input[type="email"], #email', email)
            page.fill('input[name="password"], input[type="password"], #password', password)
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=15000)

            if "login" in page.url:
                return False, "Login fallido — verifica credenciales de Computrabajo"

            # ── Navigate to job ──────────────────────────────────────────
            page.goto(job_url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # ── Click Postularme ─────────────────────────────────────────
            btn_sel = (
                'a:has-text("Postularme"), '
                'button:has-text("Postularme"), '
                'a:has-text("Aplicar"), '
                '.btn_postular, '
                '#btn_postular'
            )
            try:
                page.locator(btn_sel).first.click(timeout=8000)
            except PWTimeout:
                return False, "No se encontró el botón Postularme en Computrabajo"

            time.sleep(2)
            page.wait_for_load_state("networkidle", timeout=10000)

            # ── Handle any confirmation dialog ───────────────────────────
            confirm_sel = (
                'button:has-text("Confirmar"), '
                'button:has-text("Enviar"), '
                'button:has-text("Aceptar"), '
                'button[type="submit"]'
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


def register_computrabajo(
    name: str, email: str, password: str, phone: str = ""
) -> tuple[bool, str]:
    """
    Create a new Computrabajo Venezuela account (visible browser).
    """
    _check()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            page.goto("https://www.computrabajo.com.ve/registrarse", timeout=20000)
            page.wait_for_load_state("networkidle")

            # Fill name fields
            try:
                page.fill('input[name="nombre"], input[placeholder*="nombre"]', name.split()[0])
                if len(name.split()) > 1:
                    page.fill('input[name="apellido"], input[placeholder*="apellido"]',
                              " ".join(name.split()[1:]))
            except Exception:
                pass

            page.fill('input[type="email"]', email)
            page.fill('input[type="password"]', password)
            if phone:
                try:
                    page.fill('input[name="telefono"], input[type="tel"]', phone)
                except Exception:
                    pass

            page.click('button[type="submit"], input[type="submit"]')
            time.sleep(3)

            return True, (
                "Registro enviado en Computrabajo. "
                "Revisa tu correo para verificar la cuenta."
            )
        except Exception as exc:
            return False, f"Error al registrar en Computrabajo: {exc}"
        finally:
            time.sleep(3)
            browser.close()


def is_available() -> bool:
    return PLAYWRIGHT_AVAILABLE
