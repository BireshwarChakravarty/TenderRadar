"""
TenderRadar — Tender Aggregator Scrapers
Scrapes third-party aggregator sites that consolidate Indian govt tenders.
These sites are not IP-blocked and pull from GeM, CPPP, all state portals.
"""
import re
import time
from datetime import datetime, timedelta
from base_scraper import BaseScraper, Tender

# Keywords to filter communications/PR relevant tenders
COMMS_KEYWORDS = [
    "communication", "pr agency", "public relations", "media relations",
    "social media", "digital outreach", "campaign", "awareness campaign",
    "content development", "creative agency", "media monitoring", "event publicity",
    "reputation", "brand", "empanelment", "outreach", "digital media",
    "advertising", "media management", "press", "publicity", "public awareness",
    "integrated communication", "digital engagement", "analytics", "media buying",
    "influencer", "production house", "film production", "documentary",
]


def is_relevant(title: str, desc: str = "") -> bool:
    text = (title + " " + desc).lower()
    return any(k in text for k in COMMS_KEYWORDS)


class TenderWizardScraper(BaseScraper):
    PORTAL_NAME = "TenderWizard"
    BASE = "https://www.tenderwizard.com"
    SEARCH_URLS = [
        "https://www.tenderwizard.com/INDIA/tender/keywords/communication",
        "https://www.tenderwizard.com/INDIA/tender/keywords/social+media",
        "https://www.tenderwizard.com/INDIA/tender/keywords/pr+agency",
        "https://www.tenderwizard.com/INDIA/tender/keywords/media+management",
    ]

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting TenderWizard scrape…")
        for url in self.SEARCH_URLS:
            try:
                time.sleep(3)
                soup = self.get(url)
                if not soup:
                    continue
                rows = (
                    soup.select("table.tender-table tbody tr") or
                    soup.select(".tender-list .tender-item") or
                    soup.select(".tenderblock") or
                    soup.select("table tbody tr") or
                    soup.select(".tender_row") or
                    soup.select("[class*='tender']")
                )
                for row in rows:
                    t = self._parse(row)
                    if t:
                        tenders.append(t)
                self.logger.info(f"TenderWizard {url.split('/')[-1]}: {len(tenders)} so far")
            except Exception as e:
                self.logger.error(f"TenderWizard {url}: {e}")
        seen = set()
        unique = []
        for t in tenders:
            if t.id not in seen:
                seen.add(t.id)
                unique.append(t)
        self.logger.info(f"TenderWizard total: {len(unique)}")
        return unique

    def _parse(self, row) -> Tender | None:
        try:
            text = row.get_text(" ", strip=True)
            if len(text) < 10:
                return None
            link  = row.select_one("a[href]")
            cells = row.find_all("td")
            title_el = row.select_one("h3,h4,.title,.tender-title,td:nth-child(2),td:nth-child(1)")
            title = title_el.get_text(strip=True) if title_el else (cells[1].get_text(strip=True) if len(cells) > 1 else text[:200])
            if not title or len(title) < 5:
                return None
            if not is_relevant(title, text):
                return None
            ref_m = re.search(r"[\w/\-]{5,30}/\d{4}", text)
            ref   = ref_m.group(0) if ref_m else f"TW-{title[:20].replace(' ','')}"
            dm    = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
            dl    = self._pd(dm.group(0)) if dm else self._dd(30)
            href  = link.get("href","") if link else ""
            url   = (self.BASE + href) if href.startswith("/") else (href if href.startswith("http") else self.BASE)
            val_m = re.search(r"[₹Rs]+\s*[\d,\.]+\s*(Cr|L|K)?", text, re.IGNORECASE)
            val   = val_m.group(0) if val_m else "N/A"
            return self.make_tender(
                title=title[:250], ref_no=ref[:100],
                category=self._cat(title), description=text[:400],
                value_raw=0.0, value_str=val, deadline=dl, url=url,
            )
        except Exception as e:
            self.logger.debug(f"TW parse: {e}")
            return None

    def _pd(self, s):
        for f in ("%d/%m/%Y","%d-%m-%Y","%Y-%m-%d","%d/%m/%y","%d-%b-%Y"):
            try: return datetime.strptime(s.strip()[:10], f).strftime("%Y-%m-%d")
            except: pass
        return self._dd(30)

    def _dd(self, d): return (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")

    def _cat(self, t):
        t = t.lower()
        if any(k in t for k in ["pr ","public relation","communication","empanelment"]): return "PR & Communications"
        if any(k in t for k in ["social media","digital media"]): return "Social Media"
        if any(k in t for k in ["campaign","awareness"]): return "Campaign Execution"
        if any(k in t for k in ["monitor","clipping","sentiment"]): return "Media Monitoring"
        if any(k in t for k in ["event","exhibition","fair"]): return "Event Publicity"
        if any(k in t for k in ["creative","content","design","film"]): return "Creative & Content"
        if any(k in t for k in ["reputation","crisis","brand"]): return "Reputation Management"
        if any(k in t for k in ["analytics","reporting","dashboard"]): return "Analytics"
        return "Communication Support"


class TendersOnTimeScraper(BaseScraper):
    PORTAL_NAME = "TendersOnTime"
    SEARCH_URLS = [
        "https://www.tendersontime.com/search-tenders/?keyword=communication+agency",
        "https://www.tendersontime.com/search-tenders/?keyword=social+media+management",
        "https://www.tendersontime.com/search-tenders/?keyword=pr+empanelment",
        "https://www.tendersontime.com/search-tenders/?keyword=media+monitoring",
    ]

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting TendersOnTime scrape…")
        for url in self.SEARCH_URLS:
            try:
                time.sleep(3)
                soup = self.get(url)
                if not soup:
                    continue
                rows = (
                    soup.select(".tender-list-item") or
                    soup.select(".tender_item") or
                    soup.select("table tbody tr") or
                    soup.select(".tenderRow") or
                    soup.select("[class*='tender']")
                )
                for row in rows:
                    t = self._parse(row, url)
                    if t:
                        tenders.append(t)
            except Exception as e:
                self.logger.error(f"TendersOnTime {url}: {e}")
        seen = set()
        unique = [t for t in tenders if t.id not in seen and not seen.add(t.id)]
        self.logger.info(f"TendersOnTime total: {len(unique)}")
        return unique

    def _parse(self, row, base_url) -> Tender | None:
        try:
            text = row.get_text(" ", strip=True)
            if len(text) < 10:
                return None
            link  = row.select_one("a[href]")
            title_el = row.select_one("h2,h3,h4,.title,strong,.tender-title")
            title = title_el.get_text(strip=True) if title_el else text[:200]
            if not title or len(title) < 5:
                return None
            if not is_relevant(title, text):
                return None
            ref_m = re.search(r"[\w/\-]{5,30}/\d{4}", text)
            ref   = ref_m.group(0) if ref_m else f"TOT-{title[:20].replace(' ','')}"
            dm    = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
            dl    = self._pd(dm.group(0)) if dm else self._dd(30)
            href  = link.get("href","") if link else ""
            url   = href if href.startswith("http") else ("https://www.tendersontime.com" + href)
            return self.make_tender(
                title=title[:250], ref_no=ref[:100],
                category=self._cat(title), description=text[:400],
                value_raw=0.0, value_str="N/A", deadline=dl, url=url,
            )
        except Exception: return None

    def _pd(self, s):
        for f in ("%d/%m/%Y","%d-%m-%Y","%Y-%m-%d"):
            try: return datetime.strptime(s.strip()[:10], f).strftime("%Y-%m-%d")
            except: pass
        return self._dd(30)

    def _dd(self, d): return (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")

    def _cat(self, t):
        t = t.lower()
        if any(k in t for k in ["pr ","public relation","communication","empanelment"]): return "PR & Communications"
        if any(k in t for k in ["social media","digital"]): return "Social Media"
        if any(k in t for k in ["campaign","awareness"]): return "Campaign Execution"
        if any(k in t for k in ["monitor","clipping"]): return "Media Monitoring"
        if any(k in t for k in ["event","exhibition"]): return "Event Publicity"
        if any(k in t for k in ["creative","content","design"]): return "Creative & Content"
        return "Communication Support"


class ETendersScraper(BaseScraper):
    PORTAL_NAME = "eTenders"
    SEARCH_URLS = [
        "https://etenders.in/tender/communication-agency-tenders",
        "https://etenders.in/tender/social-media-tenders",
        "https://etenders.in/tender/pr-agency-tenders",
    ]

    def scrape(self) -> list[Tender]:
        tenders = []
        self.logger.info("Starting eTenders scrape…")
        for url in self.SEARCH_URLS:
            try:
                time.sleep(3)
                soup = self.get(url)
                if not soup:
                    continue
                rows = (
                    soup.select("table tbody tr") or
                    soup.select(".tender-item") or
                    soup.select("[class*='tender']")
                )
                for row in rows:
                    t = self._parse(row)
                    if t:
                        tenders.append(t)
            except Exception as e:
                self.logger.error(f"eTenders {url}: {e}")
        seen = set()
        unique = [t for t in tenders if t.id not in seen and not seen.add(t.id)]
        self.logger.info(f"eTenders total: {len(unique)}")
        return unique

    def _parse(self, row) -> Tender | None:
        try:
            text = row.get_text(" ", strip=True)
            if len(text) < 10:
                return None
            link  = row.select_one("a[href]")
            title_el = row.select_one("h2,h3,h4,.title,strong,td:nth-child(2)")
            title = title_el.get_text(strip=True) if title_el else text[:200]
            if not title or len(title) < 5:
                return None
            dm  = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
            dl  = self._pd(dm.group(0)) if dm else self._dd(30)
            href = link.get("href","") if link else ""
            url  = href if href.startswith("http") else ("https://etenders.in" + href)
            return self.make_tender(
                title=title[:250], ref_no=f"ET-{title[:20].replace(' ','')}",
                category=self._cat(title), description=text[:400],
                value_raw=0.0, value_str="N/A", deadline=dl, url=url,
            )
        except Exception: return None

    def _pd(self, s):
        for f in ("%d/%m/%Y","%d-%m-%Y","%Y-%m-%d"):
            try: return datetime.strptime(s.strip()[:10], f).strftime("%Y-%m-%d")
            except: pass
        return self._dd(30)

    def _dd(self, d): return (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")

    def _cat(self, t):
        t = t.lower()
        if any(k in t for k in ["pr ","communication","empanelment"]): return "PR & Communications"
        if any(k in t for k in ["social media"]): return "Social Media"
        if any(k in t for k in ["campaign","awareness"]): return "Campaign Execution"
        if any(k in t for k in ["event","exhibition"]): return "Event Publicity"
        if any(k in t for k in ["creative","content","design"]): return "Creative & Content"
        return "Communication Support"


def scrape_all_aggregators() -> list[Tender]:
    import logging
    log = logging.getLogger("Aggregators")
    all_tenders = []
    for Cls in [TenderWizardScraper, TendersOnTimeScraper, ETendersScraper]:
        try:
            results = Cls().scrape()
            all_tenders.extend(results)
            log.info(f"{Cls.PORTAL_NAME}: {len(results)} tenders")
        except Exception as e:
            log.error(f"{Cls.__name__} failed: {e}")
    return all_tenders
