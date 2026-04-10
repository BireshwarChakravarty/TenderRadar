"""
TenderRadar — RSS/Feed based scraper
Uses publicly available RSS/Atom feeds from portals.
These are not blocked because portals publish them intentionally.
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from base_scraper import BaseScraper, Tender


FEEDS = [
    # CPPP / eProcure — central government tenders
    {
        "portal": "CPPP",
        "urls": [
            "https://eprocure.gov.in/eprocure/app?component=rss&page=FrontEndLatestActiveTenders&service=direct",
            "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndLatestActiveTenders&service=direct&rss=true",
        ]
    },
    # GeM tender notices RSS
    {
        "portal": "GeM",
        "urls": [
            "https://bidplus.gem.gov.in/rss/bids",
            "https://gem.gov.in/feeds/tenders",
        ]
    },
    # MoD / Defence procurement
    {
        "portal": "MoD",
        "urls": [
            "https://mod.gov.in/rss.xml",
            "https://defproc.gov.in/rss",
        ]
    },
    # PIB (Press Information Bureau) — often has empanelment/PR tenders
    {
        "portal": "PIB",
        "urls": [
            "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
            "https://pib.gov.in/indexd.aspx",
        ]
    },
]


class RSSFeedScraper(BaseScraper):
    PORTAL_NAME = "RSS"

    def scrape_feed(self, portal: str, urls: list) -> list[Tender]:
        tenders = []
        for url in urls:
            try:
                self.logger.info(f"{portal} RSS — trying {url}")
                time.sleep(2)
                resp = self.session.get(url, timeout=15)
                if not resp.ok:
                    continue
                content = resp.text
                if not content.strip():
                    continue
                # Parse RSS/Atom
                items = self._parse_feed(content)
                for item in items:
                    t = self._item_to_tender(item, portal, url)
                    if t:
                        tenders.append(t)
                if tenders:
                    self.logger.info(f"{portal} RSS — got {len(tenders)} items")
                    break
            except Exception as e:
                self.logger.warning(f"{portal} RSS {url}: {e}")
        return tenders

    def _parse_feed(self, content: str) -> list[dict]:
        items = []
        try:
            # Strip namespace issues
            content = re.sub(r'\sxmlns[^"]*"[^"]*"', '', content)
            content = re.sub(r'<\?xml[^>]*\?>', '', content)
            root = ET.fromstring(content.strip())

            # RSS 2.0
            for item in root.findall('.//item'):
                d = {}
                for child in item:
                    tag = child.tag.split('}')[-1].lower()
                    d[tag] = (child.text or '').strip()
                if d:
                    items.append(d)

            # Atom
            if not items:
                for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                    d = {}
                    for child in entry:
                        tag = child.tag.split('}')[-1].lower()
                        d[tag] = (child.text or child.get('href', '') or '').strip()
                    if d:
                        items.append(d)
        except Exception as e:
            self.logger.debug(f"Feed parse error: {e}")
        return items

    def _item_to_tender(self, item: dict, portal: str, feed_url: str) -> Tender | None:
        try:
            title = item.get('title', '') or item.get('name', '')
            if not title or len(title) < 5:
                return None
            desc  = item.get('description', '') or item.get('summary', '') or title
            url   = item.get('link', '') or item.get('href', '') or feed_url
            pub   = item.get('pubdate', '') or item.get('published', '') or item.get('updated', '')
            dl    = self._parse_date_from_text(desc + ' ' + title) or self._dd(30)

            # Clean HTML from description
            desc = re.sub(r'<[^>]+>', ' ', desc).strip()[:500]

            self.PORTAL_NAME = portal
            return self.make_tender(
                title=title[:250],
                ref_no=self._extract_ref(title + ' ' + desc, portal),
                category=self._cat(title),
                description=desc,
                value_raw=0.0,
                value_str=self._extract_value(desc),
                deadline=dl,
                url=url,
            )
        except Exception as e:
            self.logger.debug(f"Item convert: {e}")
            return None

    def _extract_ref(self, text: str, portal: str) -> str:
        patterns = [
            r'[A-Z]{2,}/\d{4}[/-]\w+',
            r'\d{4,}/\w+/\d{2,4}',
            r'GEM[-/]\w+[-/]\w+',
            r'CPPP[-/]\d+',
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                return m.group(0)[:100]
        return f"{portal}-{text[:15].replace(' ','').replace('/','')}"

    def _extract_value(self, text: str) -> str:
        m = re.search(r'[₹Rs\.]+\s*([\d,\.]+)\s*(Cr|L|Lac|Lakh|K)?', text, re.IGNORECASE)
        if m:
            return '₹' + m.group(1) + (' ' + m.group(2) if m.group(2) else '')
        return "N/A"

    def _parse_date_from_text(self, text: str) -> str:
        for pat in [r'\b(\d{4}-\d{2}-\d{2})\b', r'\b(\d{2}/\d{2}/\d{4})\b', r'\b(\d{2}-\d{2}-\d{4})\b']:
            m = re.search(pat, text)
            if m:
                s = m.group(1)
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
                    except: pass
        return ''

    def _dd(self, d): return (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")

    def _cat(self, t):
        t = t.lower()
        if any(k in t for k in ["pr ","public relation","communication","empanelment","media relation","press release"]): return "PR & Communications"
        if any(k in t for k in ["social media","digital media","facebook","twitter","instagram"]): return "Social Media"
        if any(k in t for k in ["campaign","awareness","outreach","advertising"]): return "Campaign Execution"
        if any(k in t for k in ["monitor","clipping","sentiment","media analytic"]): return "Media Monitoring"
        if any(k in t for k in ["event","exhibition","fair","conference","seminar"]): return "Event Publicity"
        if any(k in t for k in ["creative","content","design","film","video","photography","production"]): return "Creative & Content"
        if any(k in t for k in ["reputation","crisis","brand management"]): return "Reputation Management"
        if any(k in t for k in ["analytics","reporting","dashboard","metrics","measurement"]): return "Analytics"
        return "Communication Support"

    def scrape(self) -> list[Tender]:
        return []


def scrape_all_rss() -> list[Tender]:
    scraper = RSSFeedScraper()
    all_tenders = []
    for feed in FEEDS:
        try:
            tenders = scraper.scrape_feed(feed["portal"], feed["urls"])
            all_tenders.extend(tenders)
            import logging
            logging.getLogger("RSS").info(f"{feed['portal']}: {len(tenders)} tenders via RSS")
        except Exception as e:
            import logging
            logging.getLogger("RSS").error(f"{feed['portal']} RSS failed: {e}")
    return all_tenders
