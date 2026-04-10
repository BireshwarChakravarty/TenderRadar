"""
TenderRadar — BHEL Tender Scraper
Scrapes: https://www.bhel.com/tender-notices
Public tender listing, no login.
"""
import re
from datetime import datetime
from base_scraper import BaseScraper, Tender


class BHELScraper(BaseScraper):
    PORTAL_NAME = "BHEL"
    BASE_URL    = "https://www.bhel.com/tender-notices"
    ALT_URL     = "https://www.bhel.com/tenders"

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting BHEL scrape…")

        for url in [self.BASE_URL, self.ALT_URL]:
            soup = self.get(url)
            if not soup:
                continue

            rows = soup.select(
                "table tbody tr, .tender-list li, .views-row, "
                ".tender-item, article.node--type-tender"
            )

            if not rows:
                # Fallback: look for any table
                rows = soup.select("tr")

            for row in rows:
                t = self._parse_row(row, url)
                if t:
                    tenders.append(t)

            if tenders:
                break

        self.logger.info(f"BHEL — scraped {len(tenders)} tenders")
        return tenders

    def _parse_row(self, row, base_url: str) -> Tender | None:
        try:
            text  = row.get_text(" ", strip=True)
            if len(text) < 15:
                return None

            # Extract title from link text or largest text chunk
            link  = row.select_one("a")
            title = link.get_text(strip=True) if link else text[:200]
            if not title or len(title) < 8:
                return None

            url   = (base_url + link["href"]) if (link and link.get("href","").startswith("/")) else (link["href"] if link else base_url)

            # Try to parse ref number from text
            ref_m = re.search(r"(BHEL[\/\-\s][\w\/\-]+|\d{2,}\/\w+\/\d{4})", text, re.IGNORECASE)
            ref   = ref_m.group(0) if ref_m else f"BHEL-{title[:20].replace(' ','')}"

            # Try to parse deadline
            date_m = re.search(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", text)
            deadline = self._parse_date(date_m.group(0)) if date_m else ""

            return self.make_tender(
                title=title[:250],
                ref_no=ref[:100],
                category=self._infer_category(title),
                description=title,
                value_raw=0.0,
                value_str="N/A",
                deadline=deadline,
                url=url,
            )
        except Exception as e:
            self.logger.debug(f"BHEL row parse error: {e}")
            return None

    def _parse_date(self, text: str) -> str:
        text = text.strip().replace(".", "-")
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return ""

    def _infer_category(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["it","software","server","computer","network","laptop","hardware"]):
            return "IT Equipment"
        if any(k in t for k in ["erp","sap","oracle","crm","system implementation"]):
            return "Consulting"
        if any(k in t for k in ["amc","maintenance","service","support"]):
            return "Maintenance"
        if any(k in t for k in ["civil","construction","fabrication","structural"]):
            return "Civil Works"
        return "Supplies"
