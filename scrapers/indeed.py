"""
Indeed scraper using Playwright (no login required for search).
The RSS endpoint is blocked; Playwright renders the page properly.
"""
import re

_HTML_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _HTML_RE.sub(" ", text or "")).strip()


def search(keywords: str = "marketing", location: str = "", limit: int = 25,
           email: str = "", password: str = "") -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[Indeed] Playwright not installed — skipping")
        return []

    jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = ctx.new_page()
        try:
            # Log in if credentials provided — improves result quality
            if email and password:
                try:
                    page.goto("https://secure.indeed.com/account/login", timeout=15000)
                    page.fill('input[type="email"]', email)
                    page.click('button[type="submit"]')
                    import time; time.sleep(1.5)
                    page.fill('input[type="password"]', password)
                    page.click('button[type="submit"]')
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass  # proceed without login if it fails

            url = f"https://www.indeed.com/jobs?q={keywords}&sort=date"
            if location:
                url += f"&l={location}"
            page.goto(url, timeout=25000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Dismiss cookie / consent banners
            for sel in [
                "button#onetrust-accept-btn-handler",
                "button:has-text('Accept all')",
                "button:has-text('Accept')",
                "[aria-label='close']",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                except Exception:
                    pass

            # Wait for job cards
            try:
                page.wait_for_selector(
                    "li.css-1ac2h1w, .job_seen_beacon, li[data-jk]",
                    timeout=10000,
                )
            except PWTimeout:
                print("[Indeed] No job cards found — may be blocked")
                return []

            cards = page.locator(
                "li.css-1ac2h1w, .job_seen_beacon, li[data-jk]"
            ).all()[:limit]

            for card in cards:
                try:
                    title_el = card.locator(
                        "h2.jobTitle span[title], h2 span[title], h2 a span"
                    ).first
                    company_el = card.locator(
                        "[data-testid='company-name'], .companyName, .css-63koeb"
                    ).first
                    link_el = card.locator("a[href*='jk='], h2 a").first
                    loc_el = card.locator(
                        "[data-testid='text-location'], .companyLocation"
                    ).first
                    salary_el = card.locator(
                        "[data-testid='attribute_snippet_testid'], .salary-snippet"
                    ).first

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

                    href = link_el.get_attribute("href") or ""
                    if href and not href.startswith("http"):
                        href = "https://www.indeed.com" + href

                    loc_str = ""
                    try:
                        loc_str = loc_el.inner_text(timeout=2000).strip()
                    except Exception:
                        pass

                    salary = ""
                    try:
                        salary = salary_el.inner_text(timeout=2000).strip()
                    except Exception:
                        pass

                    ext_id = ""
                    if "jk=" in href:
                        ext_id = href.split("jk=")[1][:20]
                    if not ext_id:
                        ext_id = re.sub(r"[^a-zA-Z0-9]", "", href)[-20:]

                    if title and href:
                        jobs.append({
                            "source": "Indeed",
                            "external_id": ext_id,
                            "title": title,
                            "company": company or "Empresa desconocida",
                            "location": loc_str or location or "Remoto",
                            "job_type": "",
                            "salary": salary,
                            "description": "",
                            "url": href,
                            "tags": [],
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[Indeed] Error: {e}")
        finally:
            browser.close()

    return jobs
