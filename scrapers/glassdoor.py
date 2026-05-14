"""
Glassdoor scraper using Playwright (no login required for search).
The site is JavaScript-rendered — requests-based scraping gets an empty shell.
"""
import re


def search(keywords: str = "marketing", location: str = "", limit: int = 25) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[Glassdoor] Playwright not installed — skipping")
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
            url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keywords}&fromAge=14"
            if location:
                url += f"&locT=C&locKeyword={location}"
            page.goto(url, timeout=25000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Dismiss modals / login walls / cookie banners
            for sel in [
                "button[data-test='modal-close-btn']",
                "button[aria-label='Close']",
                "button:has-text('Close')",
                "button#onetrust-accept-btn-handler",
                "[class*='modal'] button",
            ]:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                except Exception:
                    pass

            # Wait for job cards
            card_sel = (
                "li.react-job-listing, "
                "article[data-id], "
                "[data-test='jobListing'], "
                "li[class*='JobsList']"
            )
            try:
                page.wait_for_selector(card_sel, timeout=10000)
            except PWTimeout:
                print("[Glassdoor] No job cards found — may be blocked or login-walled")
                return []

            cards = page.locator(card_sel).all()[:limit]

            for card in cards:
                try:
                    title_el = card.locator(
                        "[data-test='job-title'], h3.JobCard_jobTitle__GLyJ1, h3, h2"
                    ).first
                    company_el = card.locator(
                        "[data-test='employer-name'], "
                        ".EmployerProfile_compactEmployerName__9MGcV, "
                        "[class*='employerName']"
                    ).first
                    link_el = card.locator("a").first
                    loc_el = card.locator(
                        "[data-test='emp-location'], [class*='location']"
                    ).first
                    salary_el = card.locator(
                        "[data-test='detailSalary'], [class*='salary']"
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
                        href = "https://www.glassdoor.com" + href

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
                    m = re.search(r"jobListingId=(\d+)", href)
                    if m:
                        ext_id = m.group(1)
                    else:
                        ext_id = re.sub(r"[^a-zA-Z0-9]", "", href)[-20:]

                    if title and href:
                        jobs.append({
                            "source": "Glassdoor",
                            "external_id": ext_id,
                            "title": title,
                            "company": company or "Empresa desconocida",
                            "location": loc_str or location or "No especificado",
                            "job_type": "",
                            "salary": salary,
                            "description": "",
                            "url": href,
                            "tags": [],
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"[Glassdoor] Error: {e}")
        finally:
            browser.close()

    return jobs
