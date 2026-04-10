"""
TenderRadar — CPPP / eProcure Scraper
Scrapes: https://eprocure.gov.in/eprocure/app
Central Public Procurement Portal — all central ministry tenders.
"""
import re
from datetime import datetime
from base_scraper import BaseScraper, Tender


class CPPPScraper(BaseScraper):
    PORTAL_NAME = "CPPP"
    SEARCH_URL  = "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByOrganisation&service=direct&session=T"
    TENDER_LIST = "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndLatestActiveTenders&service=direct&session=T"
    MAX_PAGES   = 5

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting CPPP scrape…")

        for page_num in range(1, self.MAX_PAGES + 1):
            try:
                params = {
                    "component": "$DirectLink",
                    "page": "FrontEndLatestActiveTenders",
                    "service": "direct",
                    "session": "T",
                    "pageNo": str(page_num),
                }
                soup = self.get("https://eprocure.gov.in/eprocure/app", params=params)
                if not soup:
                    break

                rows = soup.select("table.list_table tbody tr, #table tr:not(:first-child)")
                if not rows:
                    self.logger.info(f"CPPP — no rows on page {page_num}, stopping")
                    break

                page_tenders = 0
                for row in rows:
                    t = self._parse_row(row)
                    if t:
                        tenders.append(t)
                        page_tenders += 1

                self.logger.info(f"CPPP — page {page_num}: {page_tenders} tenders")
                if page_tenders == 0:
                    break

            except Exception as e:
                self.logger.error(f"CPPP page {page_num} error: {e}")
                break

        self.logger.info(f"CPPP — total scraped: {len(tenders)}")
        return tenders

    def _parse_row(self, row) -> Tender | None:
        try:
            cells = row.find_all("td")
            if len(cells) < 4:
                return None

            # Column order varies; heuristic detection
            texts = [c.get_text(strip=True) for c in cells]

            # Find reference number (usually contains /, looks like NIT/xxxx)
            ref    = ""
            title  = ""
            org    = ""
            value_str = "N/A"
            deadline  = ""

            for i, text in enumerate(texts):
                if re.search(r"\d{4,}", text) and "/" in text and not ref:
                    ref = text[:100]
                elif len(text) > 30 and not title:
                    title = text[:250]
                elif "date" in texts[i-1].lower() if i > 0 else False:
                    deadline = self._parse_date(text)

            # Try to get link
            link = row.select_one("a[href]")
            url  = ("https://eprocure.gov.in" + link["href"]) if link else "https://eprocure.gov.in"

            if not title:
                return None

            return self.make_tender(
                title=title,
                ref_no=ref or "CPPP-" + title[:20].replace(" ", ""),
                category=self._infer_category(title),
                description=title,
                value_raw=0.0,
                value_str=value_str,
                deadline=deadline,
                url=url,
            )
        except Exception as e:
            self.logger.debug(f"CPPP row parse error: {e}")
            return None

    def _parse_date(self, text: str) -> str:
        text = text.strip()
        for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y"):
            try:
                return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        return text[:10]

    def _infer_category(self, title: str) -> str:
        t = title.lower()
        if any(k in t for k in ["laptop","server","network","it ","software","hardware","computer","cctv"]):
            return "IT Equipment"
        if any(k in t for k in ["road","bridge","civil","construction","building"]):
            return "Civil Works"
        if any(k in t for k in ["solar","power","electrical","panel","transformer"]):
            return "Infrastructure"
        if any(k in t for k in ["amc","maintenance","support","service"]):
            return "Maintenance"
        if any(k in t for k in ["consult","advisory","study","survey"]):
            return "Consulting"
        return "Supplies"
