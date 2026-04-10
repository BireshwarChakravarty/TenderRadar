"""
TenderRadar — Main Orchestrator
Priority: Aggregator sites → BHEL (works) → others as fallback
"""
import logging, sys, json
from datetime import datetime
from config import SCRAPE_GEM, SCRAPE_CPPP, SCRAPE_BHEL, SCRAPE_ONGC, SCRAPE_NTPC, SCRAPE_STATE
from deduplicator import merge_new_tenders, load_existing, save_tenders
from ai_scorer import score_tenders

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S", handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("Orchestrator")


def run():
    start = datetime.utcnow()
    logger.info("=" * 60)
    logger.info(f"TenderRadar started at {start.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("=" * 60)
    all_scraped = []

    # ── Priority 1: Aggregator sites (not IP-blocked) ─────────
    logger.info("Phase 1: Aggregator sites…")
    try:
        from aggregator_scrapers import scrape_all_aggregators
        results = scrape_all_aggregators()
        all_scraped.extend(results)
        logger.info(f"✓ Aggregators: {len(results)} tenders")
    except Exception as e:
        logger.error(f"✗ Aggregators failed: {e}")

    # ── Priority 2: BHEL (confirmed working) ──────────────────
    if SCRAPE_BHEL:
        try:
            from bhel_scraper import BHELScraper
            results = BHELScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ BHEL: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ BHEL failed: {e}")

    # ── Priority 3: Others (may be blocked) ───────────────────
    logger.info("Phase 3: Direct scrapers (may be blocked)…")

    if SCRAPE_GEM:
        try:
            from gem_scraper import GeMScraper
            results = GeMScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ GeM: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ GeM: {e}")

    if SCRAPE_CPPP:
        try:
            from cppp_scraper import CPPPScraper
            results = CPPPScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ CPPP: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ CPPP: {e}")

    if SCRAPE_ONGC:
        try:
            from psu_scrapers import ONGCScraper
            results = ONGCScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ ONGC: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ ONGC: {e}")

    if SCRAPE_NTPC:
        try:
            from psu_scrapers import NTPCScraper
            results = NTPCScraper().scrape()
            all_scraped.extend(results)
            logger.info(f"✓ NTPC: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ NTPC: {e}")

    if SCRAPE_STATE:
        try:
            from state_scrapers import scrape_all_states
            results = scrape_all_states()
            all_scraped.extend(results)
            logger.info(f"✓ State: {len(results)} tenders")
        except Exception as e:
            logger.error(f"✗ State: {e}")

    logger.info(f"\nTotal scraped (pre-dedup): {len(all_scraped)}")

    truly_new, _ = merge_new_tenders(all_scraped)
    logger.info(f"New: {len(truly_new)} / Store: {len(load_existing())}")

    if truly_new:
        logger.info("AI scoring…")
        scored = score_tenders(truly_new)
        from config import TENDERS_FILE
        if TENDERS_FILE.exists():
            with open(TENDERS_FILE) as f:
                data = json.load(f)
            existing = {t["id"]: t for t in data.get("tenders", [])}
            for t in scored:
                if t.id in existing:
                    existing[t.id]["score"]   = t.score
                    existing[t.id]["summary"] = t.summary
            save_tenders(existing)
        logger.info("Scoring done.")
    else:
        logger.info("No new tenders.")

    elapsed = (datetime.utcnow() - start).seconds
    logger.info("=" * 60)
    logger.info(f"Done in {elapsed}s | New: {len(truly_new)} | Total: {len(all_scraped)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
