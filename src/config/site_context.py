"""Shared helpers for hub region labels, sport config path resolution, and keyword seeds."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_SPORT_CONFIG_FILE = "sport.config.json"


def resolved_sport_config_path(config_dir: Path | None = None) -> Path:
    """Path to sport JSON; SPORT_CONFIG_FILE may be a filename under config_dir or an absolute path."""
    base = config_dir or Path("src/config")
    raw = (os.getenv("SPORT_CONFIG_FILE") or DEFAULT_SPORT_CONFIG_FILE).strip()
    p = Path(raw)
    if p.is_absolute():
        return p
    return base / raw


def hub_marketing_name(site: Dict[str, Any]) -> str:
    name = (site.get("hubMarketingName") or "").strip()
    if name:
        return name
    return "Metro Atlanta"


def hub_keyword_seeds(site: Dict[str, Any], sport: Dict[str, Any]) -> List[str]:
    seo = site.get("seo") or {}
    terms = seo.get("primaryHeadTerms")
    if isinstance(terms, list) and terms:
        return [str(t) for t in terms if t]
    kw = sport.get("keywords") or {}
    primary = kw.get("primary")
    if isinstance(primary, list) and primary:
        return [str(t) for t in primary if t]
    return ["pickup soccer", "soccer games"]
