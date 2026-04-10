"""
TenderRadar — ONGC Tender Scraper
Scrapes: https://www.ongcindia.com/web/guest/tender
"""
import re
from datetime import datetime
from base_scraper import BaseScraper, Tender


class ONGCScraper(BaseScraper):
    PORTAL_NAME = "ONGC"
    BASE_URL    = "https://www.ongcindia.com/web/guest/tender"

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting ONGC scrape…")

        soup = self.get(self.BASE_URL)
        if not soup:
            return tenders

        selectors = [
            ".tender-list li", "table tbody tr", ".portlet-body tr",
            ".asset-abstract", ".journal-content-article li"
        ]
        rows = []
        for sel in selectors:
            rows = soup.select(sel)
            if rows:
                break

        for row in rows:
            t = self._parse(row)
            if t:
                tenders.append(t)

        self.logger.info(f"ONGC — scraped {len(tenders)} tenders")
        return tenders

    def _parse(self, row) -> Tender | None:
        try:
            text  = row.get_text(" ", strip=True)
            if len(text) < 15:
                return None
            link  = row.select_one("a")
            title = link.get_text(strip=True) if link else text[:200]
            if not title or len(title) < 8:
                return None
            url   = link["href"] if (link and link.get("href","").startswith("http")) else self.BASE_URL
            ref_m = re.search(r"(ONGC[\/\-][\w\/\-]+|\d{2,}\/\w+\/\d{4})", text, re.IGNORECASE)
            ref   = ref_m.group(0) if ref_m else f"ONGC-{title[:20].replace(' ','')}"
            date_m = re.search(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", text)
            deadline = self._parse_date(date_m.group(0)) if date_m else ""
            return self.make_tender(
                title=title[:250], ref_no=ref[:100],
                category=self._infer_category(title),
                description=title, value_raw=0.0,
                value_str="N/A", deadline=deadline, url=url,
            )
        except Exception as e:
            self.logger.debug(f"ONGC parse error: {e}")
            return None

    def _parse_date(self, text: str) -> str:
        text = text.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return ""

    def _infer_category(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["it","software","server","computer","network","laptop"]):
            return "IT Equipment"
        if any(k in t for k in ["solar","power","electrical"]):
            return "Infrastructure"
        if any(k in t for k in ["amc","maintenance","service"]):
            return "Maintenance"
        if any(k in t for k in ["civil","construction"]):
            return "Civil Works"
        return "Supplies"


class NTPCScraper(BaseScraper):
    PORTAL_NAME = "NTPC"
    BASE_URL    = "https://www.ntpc.co.in/en/procurement/tenders"

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting NTPC scrape…")

        soup = self.get(self.BASE_URL)
        if not soup:
            return tenders

        for sel in ["table tbody tr", ".tender-item", ".views-row", "li.tender"]:
            rows = soup.select(sel)
            if rows:
                for row in rows:
                    t = self._parse(row)
                    if t:
                        tenders.append(t)
                break

        self.logger.info(f"NTPC — scraped {len(tenders)} tenders")
        return tenders

    def _parse(self, row) -> Tender | None:
        try:
            text  = row.get_text(" ", strip=True)
            if len(text) < 15:
                return None
            link  = row.select_one("a")
            title = link.get_text(strip=True) if link else text[:200]
            if not title or len(title) < 8:
                return None
            url   = link["href"] if (link and link.get("href","").startswith("http")) else self.BASE_URL
            ref_m = re.search(r"(NTPC[\/\-][\w\/\-]+|\d{2,}\/\w+\/\d{4})", text, re.IGNORECASE)
            ref   = ref_m.group(0) if ref_m else f"NTPC-{title[:20].replace(' ','')}"
            date_m = re.search(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", text)
            deadline = self._parse_date(date_m.group(0)) if date_m else ""
            return self.make_tender(
                title=title[:250], ref_no=ref[:100],
                category=self._infer_category(title),
                description=title, value_raw=0.0,
                value_str="N/A", deadline=deadline, url=url,
            )
        except Exception as e:
            self.logger.debug(f"NTPC parse error: {e}")
            return None

    def _parse_date(self, text: str) -> str:
        text = text.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return ""

    def _infer_category(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["it","software","server","computer","network"]):
            return "IT Equipment"
        if any(k in t for k in ["solar","power","electrical","grid"]):
            return "Infrastructure"
        if any(k in t for k in ["civil","construction"]):
            return "Civil Works"
        if any(k in t for k in ["amc","maintenance","service"]):
            return "Maintenance"
        return "Supplies"
