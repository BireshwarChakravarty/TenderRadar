"""
TenderRadar — Deduplication Engine
Prevents duplicate tenders from multiple scrape runs and cross-portal duplicates.
"""
import json
import logging
from pathlib import Path
from base_scraper import Tender
from config import TENDERS_FILE

logger = logging.getLogger("Deduplicator")


def load_existing() -> dict[str, dict]:
    """Load existing tenders as {id: tender_dict}."""
    if not TENDERS_FILE.exists():
        return {}
    try:
        with open(TENDERS_FILE) as f:
            data = json.load(f)
        return {t["id"]: t for t in data.get("tenders", []) if t.get("id")}
    except Exception as e:
        logger.error(f"Failed to load existing tenders: {e}")
        return {}


def save_tenders(tender_dict: dict[str, dict]) -> None:
    """Save all tenders back to JSON file."""
    tenders_list = sorted(
        tender_dict.values(),
        key=lambda t: t.get("scraped_at", ""),
        reverse=True
    )
    # Keep last 1000 tenders max
    tenders_list = tenders_list[:1000]

    out = {
        "tenders": tenders_list,
        "meta": {
            "total": len(tenders_list),
            "portals": list({t["portal"] for t in tenders_list}),
        }
    }
    with open(TENDERS_FILE, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved {len(tenders_list)} tenders to {TENDERS_FILE}")


def merge_new_tenders(new_tenders: list[Tender]) -> tuple[list[Tender], list[Tender]]:
    """
    Merge new tenders into the existing store.
    Returns (truly_new, all_merged_list).
    """
    existing = load_existing()
    truly_new = []

    for t in new_tenders:
        if t.id not in existing:
            truly_new.append(t)
            existing[t.id] = t.to_dict()
        else:
            # Preserve user-set status and score if already tracked
            stored = existing[t.id]
            if stored.get("status", "New") != "New":
                continue  # Don't overwrite user pipeline status
            # Update deadline and url in case they changed
            stored["deadline"]   = t.deadline or stored.get("deadline", "")
            stored["url"]        = t.url or stored.get("url", "")
            stored["scraped_at"] = t.scraped_at

    save_tenders(existing)
    logger.info(f"New tenders this run: {len(truly_new)} / Total in store: {len(existing)}")
    return truly_new, list(existing.values())
