"""
TenderRadar — Main Orchestrator
Runs all enabled scrapers, scores new tenders with Claude, saves to JSON.
Called by GitHub Actions on cron schedule.
"""
import logging
import sys
from datetime import datetime

from config import (
    SCRAPE_GEM, SCRAPE_CPPP, SCRAPE_BHEL, SCRAPE_ONGC, SCRAPE_NTPC, SCRAPE_STATE
)
from deduplicator import merge_new_tenders, load_existing, save_tenders
from ai_scorer import score_tenders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Orchestrator")


def run():
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info(f"TenderRadar scrape started at {start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("=" * 60)

    all_scraped = []

    # ── GeM ──────────────────────────────────────────────────────
    if SCRAPE_GEM:
        try:
            from gem_scraper import GeMScraper
            results = GeMScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ GeM: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ GeM failed: {e}")

    # ── CPPP ─────────────────────────────────────────────────────
    if SCRAPE_CPPP:
        try:
            from cppp_scraper import CPPPScraper
            results = CPPPScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ CPPP: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ CPPP failed: {e}")

    # ── PSU portals ───────────────────────────────────────────────
    if SCRAPE_BHEL:
        try:
            from psu_scrapers import BHELScraper
            results = BHELScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ BHEL: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ BHEL failed: {e}")

    if SCRAPE_ONGC:
        try:
            from psu_scrapers import ONGCScraper
            results = ONGCScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ ONGC: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ ONGC failed: {e}")

    if SCRAPE_NTPC:
        try:
            from psu_scrapers import NTPCScraper
            results = NTPCScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ NTPC: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ NTPC failed: {e}")

    # ── State portals ─────────────────────────────────────────────
    if SCRAPE_STATE:
        try:
            from state_scrapers import scrape_all_states
            results = scrape_all_states()
            all_scraped.extend(results)
            logger.info(f"✓ State portals: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ State portals failed: {e}")

    logger.info(f"\nTotal scraped (pre-dedup): {len(all_scraped)}")

    # ── Deduplicate ───────────────────────────────────────────────
    truly_new, _ = merge_new_tenders(all_scraped)
    logger.info(f"Truly new (not seen before): {len(truly_new)}")

    # ── AI Score new tenders ──────────────────────────────────────
    if truly_new:
        logger.info("Running AI relevance scoring…")
        scored = score_tenders(truly_new)

        # Write scores back to the stored JSON
        existing = {}
        from config import TENDERS_FILE
        import json
        if TENDERS_FILE.exists():
            with open(TENDERS_FILE) as f:
                data = json.load(f)
            existing = {t["id"]: t for t in data.get("tenders", [])}

        for t in scored:
            if t.id in existing:
                existing[t.id]["score"]   = t.score
                existing[t.id]["summary"] = t.summary

        save_tenders(existing)
        logger.info("AI scoring complete, scores saved.")
    else:
        logger.info("No new tenders — skipping AI scoring.")

    elapsed = (datetime.utcnow() - start).seconds
    logger.info("=" * 60)
    logger.info(f"Run complete in {elapsed}s | New: {len(truly_new)} | Total: {len(all_scraped)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
