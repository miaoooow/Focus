"""Built-in cat appearances shared by the web UI and native alert."""

from __future__ import annotations

from pathlib import Path

from .custom_pets import (
    custom_pet_asset_path,
    custom_pet_exists,
    custom_pet_id_from_skin,
)
from .paths import resource_root


DEFAULT_CAT_SKIN = "tuxedo"

CAT_SKINS = {
    "orange": {
        "name": "橘子汽水",
        "description": "圆脸橘猫，小时候好奇，长大后很会催进度",
        "asset": "cat-story-skins/orange-adult-v2.png",
        "young_asset": "cat-story-skins/orange-young-v2.png",
    },
    "tuxedo": {
        "name": "奶牛警长",
        "description": "黑白燕尾服，从呆萌幼猫长成冷脸警长",
        "asset": "cat-story-skins/tuxedo-adult-v2.png",
        "young_asset": "cat-story-skins/tuxedo-young-v2.png",
    },
    "ragdoll": {
        "name": "云朵布偶",
        "description": "奶油长毛猫，幼年软糯，成年后温柔记账",
        "asset": "cat-story-skins/ragdoll-adult-v2.png",
        "young_asset": "cat-story-skins/ragdoll-young-v2.png",
    },
}


def normalize_cat_skin(skin_id: str | None) -> str:
    """Return a valid built-in or locally generated skin id."""
    candidate = str(skin_id or "").strip().casefold()
    if candidate in CAT_SKINS:
        return candidate
    custom_id = custom_pet_id_from_skin(candidate)
    if custom_id and custom_pet_exists(custom_id):
        return candidate
    return DEFAULT_CAT_SKIN


def require_cat_skin(skin_id: str | None) -> str:
    """Validate an explicit skin choice and raise a user-facing error."""
    candidate = str(skin_id or "").strip().casefold()
    if candidate not in CAT_SKINS:
        raise ValueError("这只小猫还没住进猫窝")
    return candidate


def cat_skin_catalog() -> list[dict]:
    return [
        {
            "id": skin_id,
            **details,
            "asset_url": f"/assets/{details['asset']}",
            "young_asset_url": f"/assets/{details['young_asset']}",
        }
        for skin_id, details in CAT_SKINS.items()
    ]


def cat_skin_asset_path(skin_id: str | None) -> Path:
    normalized = normalize_cat_skin(skin_id)
    custom_id = custom_pet_id_from_skin(normalized)
    if custom_id:
        return custom_pet_asset_path(custom_id, 2)
    details = CAT_SKINS[normalized]
    return resource_root() / "assets" / details["asset"]


def cat_growth_asset_path(skin_id: str | None, stage_index: int) -> Path:
    skin_id = normalize_cat_skin(skin_id)
    custom_id = custom_pet_id_from_skin(skin_id)
    if custom_id:
        return custom_pet_asset_path(custom_id, stage_index)
    if int(stage_index) <= 1:
        details = CAT_SKINS[skin_id]
        young = resource_root() / "assets" / details["young_asset"]
        if young.exists():
            return young
    return cat_skin_asset_path(skin_id)
