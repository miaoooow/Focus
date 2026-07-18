"""Small local persistence layer for long-term focus rewards."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .cat_skins import DEFAULT_CAT_SKIN, cat_skin_catalog, normalize_cat_skin, require_cat_skin
from .custom_pets import CustomPetStore, custom_pet_id_from_skin
from .paths import user_data_root
from .penalties import penalty_snapshot


DEFAULT_PROFILE = {
    "schema_version": 1,
    "xp": 0,
    "coins": 0,
    "total_minutes": 0,
    "completed_sessions": 0,
    "clean_sessions": 0,
    "aborted_sessions": 0,
    "current_streak": 0,
    "best_streak": 0,
    "last_focus_date": "",
    "cat_name": "Luna",
    "cat_skin": DEFAULT_CAT_SKIN,
    "history": [],
}


# Growth never goes backwards: only completed focus minutes feed the kitten.
# The thresholds are intentionally close at the beginning so a new user can
# see a meaningful change in the first few sessions.
PET_STAGES = (
    (0, "刚到家的幼猫"),
    (60, "会认主的小猫"),
    (240, "活力少年猫"),
    (600, "专注陪伴猫"),
    (1500, "专注守护猫"),
)


class FocusProfileStore:
    def __init__(
        self,
        path: Path | None = None,
        custom_pets: CustomPetStore | None = None,
    ):
        self.path = path or user_data_root() / "focus_profile.json"
        self.custom_pets = custom_pets or CustomPetStore()
        self.data = self._load()

    def _load(self) -> dict:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                raise ValueError
            # Migrate names that were fixed placeholders in older prototypes;
            # user-selected names are always preserved.
            if payload.get("cat_name") in {"橘子", "小灰团"}:
                payload["cat_name"] = DEFAULT_PROFILE["cat_name"]
            return {**DEFAULT_PROFILE, **payload}
        except (OSError, ValueError, TypeError):
            return {**DEFAULT_PROFILE, "history": []}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

    def snapshot(self) -> dict:
        xp = int(self.data["xp"])
        level = xp // 250 + 1
        level_start = (level - 1) * 250
        total_minutes = int(self.data["total_minutes"])
        completed = int(self.data["completed_sessions"])
        clean = int(self.data.get("clean_sessions", 0))
        streak = int(self.data["current_streak"])
        badge_specs = (
            ("first", "第一次认真", "完成1轮专注", completed, 1),
            ("hour", "猫粮储备", "累计专注60分钟", total_minutes, 60),
            ("clean3", "零偏航选手", "完成3轮零提醒专注", clean, 3),
            ("streak7", "七日巡逻队", "连续专注7天", streak, 7),
            ("ten_hours", "时间炼金术", "累计专注600分钟", total_minutes, 600),
        )
        badges = [
            {
                "id": badge_id,
                "name": name,
                "description": description,
                "progress": min(target, value),
                "target": target,
                "unlocked": value >= target,
            }
            for badge_id, name, description, value, target in badge_specs
        ]
        history = list(self.data.get("history", []))
        weekly_minutes = []
        today = date.today()
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            minutes = sum(
                int(item.get("minutes", 0))
                for item in history
                if item.get("date") == day.isoformat() and item.get("completed")
            )
            weekly_minutes.append({"date": day.isoformat(), "minutes": minutes})
        accessories = ["红围巾"]
        if level >= 3:
            accessories.append("专注耳机")
        if level >= 5:
            accessories.append("学霸眼镜")
        pet = self._pet_snapshot(total_minutes)
        return {
            **self.data,
            "level": level,
            "level_progress": xp - level_start,
            "level_target": 250,
            "cat_stage": pet["stage"],
            "pet": pet,
            "cat_skins": [*cat_skin_catalog(), *self.custom_pets.catalog()],
            "accessories": accessories,
            "badges": badges,
            "next_badge": next((item for item in badges if not item["unlocked"]), None),
            "weekly_minutes": weekly_minutes,
        }

    def _pet_snapshot(self, total_minutes: int | None = None) -> dict:
        total = max(
            0,
            int(self.data.get("total_minutes", 0) if total_minutes is None else total_minutes),
        )
        stage_index = max(
            index for index, (threshold, _name) in enumerate(PET_STAGES)
            if total >= threshold
        )
        stage_start, stage = PET_STAGES[stage_index]
        if stage_index + 1 < len(PET_STAGES):
            next_threshold, next_stage = PET_STAGES[stage_index + 1]
            span = max(1, next_threshold - stage_start)
            progress = (total - stage_start) / span * 100
            remaining = max(0, next_threshold - total)
        else:
            next_threshold, next_stage = total, "继续一起长大"
            progress = 100
            remaining = 0

        last_text = str(self.data.get("last_focus_date") or "")
        try:
            last = date.fromisoformat(last_text)
        except ValueError:
            last = None
        today = date.today()
        if last == today:
            mood = "刚吃饱一顿专注猫粮，正在呼噜呼噜"
        elif last == today - timedelta(days=1):
            mood = "在窝里等你，尾巴已经偷偷翘起来了"
        elif last:
            mood = "有点想你，但不会掉等级，也不会饿坏"
        else:
            mood = "等着第一顿专注猫粮，也等着认识你"

        return {
            "name": str(self.data.get("cat_name") or DEFAULT_PROFILE["cat_name"]),
            "skin": self._normalize_skin(self.data.get("cat_skin")),
            "stage": stage,
            "stage_index": stage_index,
            "growth_minutes": total,
            "stage_start_minutes": stage_start,
            "next_stage": next_stage,
            "next_stage_minutes": next_threshold,
            "minutes_to_next_stage": remaining,
            "progress_percent": round(max(0, min(100, progress)), 1),
            "meals_served": total // 25,
            "mood": mood,
        }

    def rename_cat(self, name: str) -> dict:
        name = " ".join(str(name).split())
        if not name:
            raise ValueError("先给小猫写一个名字")
        if len(name) > 12:
            raise ValueError("名字最多12个字，太长它会以为你在念论文")
        if any(character in name for character in "<>\\/{}"):
            raise ValueError("名字里换一组更温柔的字符吧")
        self.data["cat_name"] = name
        self._save()
        return self.snapshot()

    def set_cat_skin(self, skin_id: str) -> dict:
        custom_id = custom_pet_id_from_skin(skin_id)
        if custom_id:
            if not self.custom_pets.exists(custom_id):
                raise ValueError("这位自定义宠物还没住进猫窝")
            selected = f"custom:{custom_id}"
        else:
            selected = require_cat_skin(skin_id)
        self.data["cat_skin"] = selected
        self._save()
        return self.snapshot()

    def _normalize_skin(self, skin_id: str | None) -> str:
        custom_id = custom_pet_id_from_skin(skin_id)
        if custom_id and self.custom_pets.exists(custom_id):
            return f"custom:{custom_id}"
        return normalize_cat_skin(skin_id)

    def create_custom_pet(
        self,
        name: str,
        image_data: str,
        *,
        renderer: str = "local-cartoon-v1",
    ) -> dict:
        item = self.custom_pets.create(name, image_data, renderer=renderer)
        self.data["cat_name"] = item["name"]
        self.data["cat_skin"] = item["skin"]
        self._save()
        return self.snapshot()

    def delete_custom_pet(self, custom_id: str) -> dict:
        selected_id = custom_pet_id_from_skin(self.data.get("cat_skin"))
        if selected_id == custom_id:
            self.data["cat_skin"] = DEFAULT_CAT_SKIN
        self.custom_pets.delete(custom_id)
        self._save()
        return self.snapshot()

    def record_completion(self, minutes: int, alerts: int, goal: str = "") -> dict:
        minutes = max(1, int(minutes))
        alerts = max(0, int(alerts))
        previous_pet = self._pet_snapshot()
        today = date.today()
        last_text = str(self.data.get("last_focus_date") or "")
        try:
            last = date.fromisoformat(last_text)
        except ValueError:
            last = None
        if last == today:
            streak = int(self.data["current_streak"])
        elif last == today - timedelta(days=1):
            streak = int(self.data["current_streak"]) + 1
        else:
            streak = 1
        penalty = penalty_snapshot(alerts, minutes)
        base_xp = minutes * 2
        clean_bonus = max(0, 20 - penalty["xp_lost"])
        earned_xp = base_xp + clean_bonus
        earned_coins = max(1, penalty["potential_coins"] - penalty["coins_lost"])
        self.data["xp"] = int(self.data["xp"]) + earned_xp
        self.data["coins"] = int(self.data["coins"]) + earned_coins
        self.data["total_minutes"] = int(self.data["total_minutes"]) + minutes
        self.data["completed_sessions"] = int(self.data["completed_sessions"]) + 1
        if alerts == 0:
            self.data["clean_sessions"] = int(self.data.get("clean_sessions", 0)) + 1
        self.data["current_streak"] = streak
        self.data["best_streak"] = max(int(self.data["best_streak"]), streak)
        self.data["last_focus_date"] = today.isoformat()
        history = list(self.data.get("history", []))
        history.append(
            {
                "date": today.isoformat(),
                "goal": goal[:80],
                "minutes": minutes,
                "alerts": alerts,
                "xp": earned_xp,
                "coins": earned_coins,
                "coins_lost": penalty["coins_lost"],
                "focus_score": penalty["focus_score"],
                "completed": True,
            }
        )
        self.data["history"] = history[-90:]
        self._save()
        current_pet = self._pet_snapshot()
        return {
            "xp": earned_xp,
            "coins": earned_coins,
            "bonus_lost": penalty["xp_lost"],
            "focus_tax": penalty["xp_lost"],
            "coins_lost": penalty["coins_lost"],
            "focus_score": penalty["focus_score"],
            "grade": penalty["grade"],
            "streak": streak,
            "care_minutes": minutes,
            "pet_name": current_pet["name"],
            "pet_stage": current_pet["stage"],
            "grew_up": current_pet["stage_index"] > previous_pet["stage_index"],
            "minutes_to_next_stage": current_pet["minutes_to_next_stage"],
        }

    def record_aborted(self, minutes: int, goal: str = "") -> None:
        if minutes <= 0:
            return
        self.data["aborted_sessions"] = int(self.data.get("aborted_sessions", 0)) + 1
        history = list(self.data.get("history", []))
        history.append(
            {
                "date": date.today().isoformat(),
                "goal": goal[:80],
                "minutes": max(0, int(minutes)),
                "alerts": 0,
                "xp": 0,
                "coins": 0,
                "completed": False,
            }
        )
        self.data["history"] = history[-90:]
        self._save()
