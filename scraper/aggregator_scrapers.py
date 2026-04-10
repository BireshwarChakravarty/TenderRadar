"""
TenderRadar — TenderDetail.com Scraper
tenderdetail.com is accessible from GitHub Actions and aggregates
tenders from GeM, CPPP, and all state portals.
URL pattern: /Indian-tender/{keyword}-tenders
"""
import re
import time
from datetime import datetime, timedelta
from base_scraper import BaseScraper, Tender


# PR/Comms specific search keywords on tenderdetail.com
SEARCH_KEYWORDS = [
    "public-relations",
    "social-media-management",
    "media-monitoring",
    "communication-agency",
    "pr-agency",
    "digital-outreach",
    "advertising-agency",
    "event-publicity",
    "media-buying",
    "content-development",
    "digital-marketing-agency",
    "integrated-communication",
]

BASE = "https://www.tenderdetail.com"


class TenderDetailScraper(BaseScraper):
    PORTAL_NAME = "TenderDetail"

    def scrape(self) -> list[Tender]:
        tenders = []
        seen_ids = set()
        self.logger.info("Starting TenderDetail.com scrape…")

        for keyword in SEARCH_KEYWORDS:
            url = f"{BASE}/Indian-tender/{keyword}-tenders"
            try:
                time.sleep(3)
                soup = self.get(url)
                if not soup:
                    continue

                # Each tender is in a numbered div > h2 > a
                links = soup.select("h2 a[href*='/TenderNotice/']")
                if not links:
                    # Fallback selectors
                    links = soup.select("a[href*='/TenderNotice/']")

                found = 0
                for link in links:
                    t = self._parse_link(link, soup)
                    if t and t.id not in seen_ids:
                        seen_ids.add(t.id)
                        tenders.append(t)
                        found += 1

                self.logger.info(f"TenderDetail '{keyword}': {found} tenders")

            except Exception as e:
                self.logger.error(f"TenderDetail '{keyword}': {e}")

        self.logger.info(f"TenderDetail total: {len(tenders)}")
        return tenders

    def _parse_link(self, link, soup) -> Tender | None:
        try:
            title = link.get_text(strip=True)
            if not title or len(title) < 8:
                return None

            href = link.get("href", "")
            url  = href if href.startswith("http") else (BASE + href)

            # Get parent container for date/value
            parent = link.parent
            for _ in range(4):
                if parent is None:
                    break
                parent = parent.parent

            container_text = parent.get_text(" ", strip=True) if parent else ""

            # Parse due date
            date_m = re.search(r"Due\s*Date\s*:?\s*([A-Za-z]+\s+\d+,?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", container_text, re.IGNORECASE)
            if date_m:
                deadline = self._pd(date_m.group(1))
            else:
                deadline = self._dd(30)

            # Parse value
            val_m = re.search(r"([\d,\.]+)\s*(Crore|Lakh|L|Cr)", container_text, re.IGNORECASE)
            if val_m:
                num = val_m.group(1).replace(",", "")
                unit = val_m.group(2).lower()
                value_str = f"₹{val_m.group(1)} {val_m.group(2)}"
            else:
                value_str = "N/A"

            # Extract ref number from title or URL
            ref_m = re.search(r"GEM/\d+/\w/\d+|[\w]+/\d{4}[/-]\w+/\d+", title + " " + url, re.IGNORECASE)
            ref = ref_m.group(0) if ref_m else f"TD-{title[:20].replace(' ','')}"

            # Get portal source from title/ref
            portal = self._detect_portal(title + container_text)

            self.PORTAL_NAME = portal
            return self.make_tender(
                title=title[:250],
                ref_no=ref[:100],
                category=self._cat(title),
                description=title,
                value_raw=0.0,
                value_str=value_str,
                deadline=deadline,
                url=url,
            )
        except Exception as e:
            self.logger.debug(f"TenderDetail parse: {e}")
            return None

    def _detect_portal(self, text: str) -> str:
        t = text.upper()
        if "GEM/" in t:    return "GeM"
        if "CPPP" in t:    return "CPPP"
        if "BHEL" in t:    return "BHEL"
        if "ONGC" in t:    return "ONGC"
        if "NTPC" in t:    return "NTPC"
        if "IRCTC" in t:   return "IRCTC"
        return "TenderDetail"

    def _pd(self, s: str) -> str:
        s = s.strip()
        # "Apr 11, 2026" format
        try:
            return datetime.strptime(s, "%b %d, %Y").strftime("%Y-%m-%d")
        except: pass
        try:
            return datetime.strptime(s, "%B %d, %Y").strftime("%Y-%m-%d")
        except: pass
        # dd/mm/yyyy
        for f in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
            try:
                return datetime.strptime(s[:10], f).strftime("%Y-%m-%d")
            except: pass
        return self._dd(30)

    def _dd(self, d: int) -> str:
        return (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")

    def _cat(self, t: str) -> str:
        t = t.lower()
        if any(k in t for k in ["pr ", "public relation", "communication agency", "empanelment", "media relation", "press release"]): return "PR & Communications"
        if any(k in t for k in ["social media", "digital media management"]): return "Social Media"
        if any(k in t for k in ["campaign", "awareness campaign", "outreach campaign"]): return "Campaign Execution"
        if any(k in t for k in ["media monitor", "press clipping", "news monitor", "sentiment"]): return "Media Monitoring"
        if any(k in t for k in ["event", "exhibition", "trade fair", "conference"]): return "Event Publicity"
        if any(k in t for k in ["creative", "content", "design", "film production", "video production"]): return "Creative & Content"
        if any(k in t for k in ["reputation", "crisis", "brand management"]): return "Reputation Management"
        if any(k in t for k in ["analytics", "reporting", "dashboard", "measurement"]): return "Analytics"
        if any(k in t for k in ["advertising", "media buying", "ad agency"]): return "Campaign Execution"
        return "Communication Support"


def scrape_all_aggregators() -> list[Tender]:
    import logging
    log = logging.getLogger("Aggregators")
    try:
        scraper = TenderDetailScraper()
        results = scraper.scrape()
        log.info(f"TenderDetail.com: {len(results)} tenders")
        return results
    except Exception as e:
        log.error(f"TenderDetail.com failed: {e}")
        return []
