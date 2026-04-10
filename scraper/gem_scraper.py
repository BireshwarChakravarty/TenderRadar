"""
TenderRadar — GeM (Government e-Marketplace) Scraper
Scrapes: https://bidplus.gem.gov.in/all-bids
Public data, no login required.
"""
import re
import time
from datetime import datetime
from base_scraper import BaseScraper, Tender
from playwright.sync_api import sync_playwright


class GeMScraper(BaseScraper):
    PORTAL_NAME = "GeM"
    BASE_URL = "https://bidplus.gem.gov.in/all-bids"
    MAX_PAGES = 5  # scrape up to 5 pages per run (~100 tenders)

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting GeM scrape via Playwright…")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/124.0.0.0 Safari/537.36"
                )
                page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)

                for page_num in range(1, self.MAX_PAGES + 1):
                    self.logger.info(f"GeM — page {page_num}")
                    try:
                        page.wait_for_selector(".bid-list-item, .card", timeout=10000)
                    except Exception:
                        self.logger.warning(f"GeM page {page_num}: selector timeout")
                        break

                    html = page.content()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "lxml")

                    for card in soup.select(".bid-list-item, .bidItem, .card-body"):
                        t = self._parse_card(card)
                        if t:
                            tenders.append(t)

                    # Next page
                    try:
                        next_btn = page.query_selector("a[aria-label='Next'], .pagination .next:not(.disabled)")
                        if next_btn:
                            next_btn.click()
                            time.sleep(3)
                        else:
                            break
                    except Exception:
                        break

                browser.close()
        except Exception as e:
            self.logger.error(f"GeM scraper error: {e}")

        self.logger.info(f"GeM — scraped {len(tenders)} tenders")
        return tenders

    def _parse_card(self, card) -> Tender | None:
        try:
            title_el  = card.select_one(".bid-title, h5, .card-title, strong")
            ref_el    = card.select_one(".bid-no, .bidNo, [class*='bid-no']")
            value_el  = card.select_one(".bid-value, [class*='amount'], [class*='value']")
            dead_el   = card.select_one(".end-date, [class*='end-date'], [class*='deadline']")
            cat_el    = card.select_one(".category, [class*='category']")
            link_el   = card.select_one("a[href*='/bid/']")

            title = title_el.get_text(strip=True) if title_el else ""
            if not title or len(title) < 5:
                return None

            ref    = ref_el.get_text(strip=True) if ref_el else "GEM-UNKNOWN"
            value_text = value_el.get_text(strip=True) if value_el else "0"
            value_raw  = self._parse_value(value_text)
            deadline   = self._parse_date(dead_el.get_text(strip=True) if dead_el else "")
            category   = cat_el.get_text(strip=True) if cat_el else self._infer_category(title)
            url        = ("https://bidplus.gem.gov.in" + link_el["href"]) if link_el else self.BASE_URL

            return self.make_tender(
                title=title[:250],
                ref_no=ref,
                category=category,
                description=title,
                value_raw=value_raw,
                value_str=value_text or self._format_value(value_raw),
                deadline=deadline,
                url=url,
            )
        except Exception as e:
            self.logger.debug(f"Parse error: {e}")
            return None

    def _parse_value(self, text: str) -> float:
        text = re.sub(r"[₹,\s]", "", text)
        m = re.search(r"[\d.]+", text)
        if not m:
            return 0.0
        val = float(m.group())
        if "cr" in text.lower():
            val *= 1e7
        elif "l" in text.lower() or "lac" in text.lower() or "lakh" in text.lower():
            val *= 1e5
        elif "k" in text.lower():
            val *= 1e3
        return val

    def _format_value(self, v: float) -> str:
        if v >= 1e7:
            return f"₹{v/1e7:.2f} Cr"
        elif v >= 1e5:
            return f"₹{v/1e5:.2f} L"
        return f"₹{v:,.0f}"

    def _parse_date(self, text: str) -> str:
        if not text:
            return ""
        text = text.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d-%b-%Y"):
            try:
                return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return text[:10]

    def _infer_category(self, title: str) -> str:
        t = title.lower()
        mapping = {
            "PR & Communications":    ["pr agency","public relations","communication agency","communications agency","empanelment","media relations","press release","spokesperson","brand communication"],
            "Social Media Management":["social media","facebook","instagram","twitter","youtube","digital media management","community management","content calendar"],
            "Campaign Execution":     ["campaign","awareness campaign","outreach campaign","integrated campaign","launch campaign","advertising campaign"],
            "Digital Outreach":       ["digital outreach","digital awareness","digital engagement","online outreach","digital marketing","influencer"],
            "Media Monitoring":       ["media monitoring","media analysis","press clipping","news monitoring","sentiment analysis","share of voice","media analytics"],
            "Event Publicity":        ["event publicity","event communication","event management","event pr","exhibition","trade fair","conference communication"],
            "Creative & Content":     ["creative","content development","content creation","copywriting","film production","video production","photography","graphic design"],
            "Reputation Management":  ["reputation","crisis communication","brand management","image management","thought leadership"],
            "Analytics & Reporting":  ["analytics","reporting","dashboard","measurement","metrics","performance report","impact assessment"],
        }
        for cat, keywords in mapping.items():
            if any(k in t for k in keywords):
                return cat
        return "Communication Support"
