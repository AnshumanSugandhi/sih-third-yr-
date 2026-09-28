"""
exchanges.py
------------
Seeded lookup dataset and VASP identification engine for Exchange Hot Wallets & Privacy Mixers.
Loads from local exchanges_db.json dataset.
"""

import json
import os
from typing import Dict, Any, Optional, Tuple

DB_FILE_PATH = os.path.join(os.path.dirname(__file__), "exchanges_db.json")

def load_exchange_database() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load exchange and mixer datasets from local JSON file."""
    if os.path.exists(DB_FILE_PATH):
        try:
            with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("exchanges", {}), data.get("mixers", {})
        except Exception as e:
            print(f"[ExchangesDB] Warning: Failed to load {DB_FILE_PATH}: {e}")
            
    return {}, {}

EXCHANGES_DATA, MIXERS_DATA = load_exchange_database()
KNOWN_EXCHANGES = EXCHANGES_DATA
KNOWN_MIXERS = MIXERS_DATA


def check_address_entity(address: str) -> Optional[Dict[str, Any]]:
    """
    Check if a wallet address matches a known exchange VASP or mixer.
    
    Returns:
        Dict with entity_type, name, category, country, kyc_required, color, and vasp_tag.
    """
    clean_addr = address.strip()
    clean_addr_lower = clean_addr.lower()
    
    # 1. Match Exchange VASP
    for k_addr, meta in EXCHANGES_DATA.items():
        if k_addr.strip() == clean_addr or k_addr.strip().lower() == clean_addr_lower:
            source = meta.get("source", "source: tradezon/cex-list")
            return {
                "entity_type": "EXCHANGE",
                "name": meta["name"],
                "category": meta.get("category", "Regulated Exchange"),
                "country": meta.get("country", "Global"),
                "kyc_required": meta.get("kyc_required", True),
                "color": meta.get("color", "#10B981"),
                "source": source,
                "vasp_tag": f"Funds reached: {meta['name']} — VASP identified ({source})"
            }
            
    # 2. Match Mixer Contract
    for k_addr, meta in MIXERS_DATA.items():
        if k_addr.strip() == clean_addr or k_addr.strip().lower() == clean_addr_lower:
            source = meta.get("source", "source: tornado-cash/verified-contracts")
            return {
                "entity_type": "MIXER",
                "name": meta["name"],
                "category": meta.get("category", "Privacy Mixer"),
                "country": "Sanctioned / Anonymous",
                "kyc_required": False,
                "color": meta.get("color", "#EF4444"),
                "source": source,
                "vasp_tag": f"Privacy Mixer Flagged: {meta['name']} ({source})"
            }
            
    return None
