"""
TenderRadar — Base scraper
All portal scrapers inherit from this class.
"""
import time
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
import requests
from bs4 import BeautifulSoup
from config import USER_AGENT, REQUEST_DELAY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)


@dataclass
class Tender:
    id:          str = ""          # sha256 hash, filled by base class
    portal:      str = ""
    title:       str = ""
    ref_no:      str = ""
    category:    str = ""
    description: str = ""
    value_raw:   float = 0.0
    value_str:   str = ""
    deadline:    str = ""          # ISO date YYYY-MM-DD
    url:         str = ""
    status:      str = "New"       # New / Watching / Bid Submitted / Won / Lost
    score:       float = 0.0       # Claude relevance score 1-10
    summary:     str = ""          # Claude AI summary
    scraped_at:  str = ""
    alerted:     bool = False

    def compute_id(self):
        """Stable ID based on portal + ref_no + title."""
        raw = f"{self.portal}|{self.ref_no}|{self.title}".lower().strip()
        self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return self

    def to_dict(self):
        return asdict(self)


class BaseScraper(ABC):
    PORTAL_NAME: str = ""

    def __init__(self):
        self.logger = logging.getLogger(self.PORTAL_NAME)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        })

    def get(self, url: str, **kwargs) -> Optional[BeautifulSoup]:
        """GET with retry + delay."""
        for attempt in range(3):
            try:
                time.sleep(REQUEST_DELAY + attempt * 2)
                resp = self.session.get(url, timeout=20, **kwargs)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
        self.logger.error(f"All retries exhausted for {url}")
        return None

    def post(self, url: str, **kwargs) -> Optional[BeautifulSoup]:
        """POST with retry + delay."""
        for attempt in range(3):
            try:
                time.sleep(REQUEST_DELAY + attempt * 2)
                resp = self.session.post(url, timeout=20, **kwargs)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "lxml")
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
        self.logger.error(f"All retries exhausted for {url}")
        return None

    def make_tender(self, **kwargs) -> Tender:
        t = Tender(
            portal=self.PORTAL_NAME,
            scraped_at=datetime.utcnow().isoformat(),
            **kwargs
        )
        return t.compute_id()

    @abstractmethod
    def scrape(self) -> list[Tender]:
        """Return list of Tender objects."""
        ...
