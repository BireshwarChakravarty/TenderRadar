"""
TenderRadar — State Government Portal Scrapers
Covers: Uttar Pradesh, Maharashtra, Karnataka (easily extensible).
"""
import re
from datetime import datetime
from base_scraper import BaseScraper, Tender


class _StateBase(BaseScraper):
    """Shared logic for state eProcurement portals (all use similar NIC software)."""

    TENDER_PATH = "/nicgep/app?component=%24DirectLink&page=FrontEndLatestActiveTenders&service=direct&session=T"

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info(f"Starting {self.PORTAL_NAME} scrape…")

        for page_num in range(1, 4):
            try:
                url = self.BASE_URL + self.TENDER_PATH + f"&pageNo={page_num}"
                soup = self.get(url)
                if not soup:
                    break

                rows = soup.select("table.list_table tbody tr, #table tr:not(:first-child)")
                if not rows:
                    break

                page_count = 0
                for row in rows:
                    t = self._parse_row(row)
                    if t:
                        tenders.append(t)
                        page_count += 1

                if page_count == 0:
                    break

            except Exception as e:
                self.logger.error(f"{self.PORTAL_NAME} page {page_num}: {e}")
                break

        self.logger.info(f"{self.PORTAL_NAME} — scraped {len(tenders)} tenders")
        return tenders

    def _parse_row(self, row) -> Tender | None:
        try:
            cells = row.find_all("td")
            if len(cells) < 3:
                return None
            texts = [c.get_text(strip=True) for c in cells]
            text_all = " ".join(texts)

            link  = row.select_one("a")
            title = link.get_text(strip=True) if link else max(texts, key=len, default="")
            if not title or len(title) < 8:
                return None

            url = (self.BASE_URL + link["href"]) if (link and link.get("href","").startswith("/")) else self.BASE_URL

            ref_m = re.search(r"\d{4,}\/\w+\/\d{4}", text_all)
            ref   = ref_m.group(0) if ref_m else f"{self.PORTAL_NAME}-{title[:20].replace(' ','')}"

            date_m = re.search(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", text_all)
            deadline = self._parse_date(date_m.group(0)) if date_m else ""

            return self.make_tender(
                title=title[:250], ref_no=ref[:100],
                category=self._infer_category(title),
                description=title, value_raw=0.0,
                value_str="N/A", deadline=deadline, url=url,
            )
        except Exception as e:
            self.logger.debug(f"{self.PORTAL_NAME} row error: {e}")
            return None

    def _parse_date(self, text: str) -> str:
        text = text.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return ""

    def _infer_category(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["it","laptop","server","computer","network","cctv","software"]):
            return "IT Equipment"
        if any(k in t for k in ["road","bridge","civil","building","construction"]):
            return "Civil Works"
        if any(k in t for k in ["solar","power","electrical"]):
            return "Infrastructure"
        if any(k in t for k in ["amc","maintenance","service","support"]):
            return "Maintenance"
        return "Supplies"


class UPStateScraper(_StateBase):
    PORTAL_NAME = "State-UP"
    BASE_URL    = "https://etender.up.nic.in"


class MaharashtraScraper(_StateBase):
    PORTAL_NAME = "State-MH"
    BASE_URL    = "https://mahatenders.gov.in"


class KarnatakaScraper(_StateBase):
    PORTAL_NAME = "State-KA"
    BASE_URL    = "https://eproc.karnataka.gov.in"


# ── Convenience: scrape all state portals ─────────────────────────────
def scrape_all_states() -> list[Tender]:
    tenders = []
    for Cls in [UPStateScraper, MaharashtraScraper, KarnatakaScraper]:
        try:
            tenders.extend(Cls().scrape())
        except Exception as e:
            import logging
            logging.getLogger("StatePortals").error(f"{Cls.PORTAL_NAME} failed: {e}")
    return tenders
