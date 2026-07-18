"""Thread-safe application controller shared by the modern web UI."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .browser_bridge import BrowserBridge
from .cat_skins import DEFAULT_CAT_SKIN
from .cloud_ai import CloudAISettingsStore, GeminiPetClient, OpenRouterClient
from .contracts import SessionConfig, TargetRule, parse_session_response, session_config_to_dict
from .matcher import browser_domain_is_unknown, matching_rules
from .ollama_client import OllamaClient
from .penalties import penalty_snapshot
from .paths import browser_extension_root
from .profile_store import FocusProfileStore
from .recommendations import group_targets_by_scene, recommend_targets
from .runtime import FocusSessionEngine, SessionState
from .services import CopyProvider, SessionParserService
from .software_relations import RelatedSuggestion, SoftwareRelationStore
from .window_monitor import ForegroundSnapshot, activate_window, get_foreground_snapshot


@dataclass(frozen=True)
class NativeAlert:
    line: str
    target_label: str
    elapsed_seconds: int
    remaining_seconds: int
    alert_count: int = 1
    cat_name: str = "Luna"
    cat_skin: str = DEFAULT_CAT_SKIN
    cat_stage_index: int = 0
    penalty_points: int = 8
    focus_score: int = 92
    coins_at_risk: int = 2
    is_preview: bool = False


@dataclass(frozen=True)
class NativeSuggestion:
    suggestion_id: str
    label: str
    reason: str
    soft_remaining_seconds: int
    cat_name: str = "Luna"
    cat_skin: str = DEFAULT_CAT_SKIN
    cat_stage_index: int = 0


@dataclass(frozen=True)
class NativeReaction:
    kind: str
    title: str
    headline: str
    detail: str
    cat_name: str = "Luna"
    cat_skin: str = DEFAULT_CAT_SKIN
    cat_stage_index: int = 0


class FocusController:
    def __init__(
        self,
        on_alert: Callable[[NativeAlert], None] | None = None,
        on_suggestion: Callable[[NativeSuggestion], None] | None = None,
        on_reaction: Callable[[NativeReaction], None] | None = None,
    ):
        self.lock = threading.RLock()
        self.client = OllamaClient()
        self.cloud_settings = CloudAISettingsStore()
        self.cloud_text_client = OpenRouterClient(self.cloud_settings)
        self.cloud_pet_client = GeminiPetClient(self.cloud_settings)
        self.parser = SessionParserService(
            self.client,
            cloud_settings=self.cloud_settings,
            cloud_client=self.cloud_text_client,
        )
        # AI edition: plan every goal with Ollama by default and prepare most
        # reminder variations in the background without blocking monitoring.
        self.copy_provider = CopyProvider(
            self.client,
            model=self.parser.model,
            model_probability=0.8,
        )
        self.relations = SoftwareRelationStore()
        self.profile = FocusProfileStore()
        self.browser_bridge = BrowserBridge()
        self.on_alert = on_alert
        self.on_suggestion = on_suggestion
        self.on_reaction = on_reaction
        self.engine: FocusSessionEngine | None = None
        self.goal = ""
        self.dynamic_allowed: set[str] = set()
        self.dismissed_suggestions: set[str] = set()
        self.suggestions: dict[str, RelatedSuggestion] = {}
        self.notified_suggestions: set[str] = set()
        self.soft_until: dict[str, float] = {}
        self.preview_count = 0
        self.last_snapshot: ForegroundSnapshot | None = None
        self.last_compliant_hwnd = 0
        self.last_status = {
            "state": "idle",
            "remaining_seconds": 0,
            "total_seconds": 0,
            "violating": False,
            "violation_elapsed_seconds": 0,
            "target_label": "",
            "alert_count": 0,
            "current": "等待开始",
            "smart_allow": "",
            "reward": None,
            "penalty": penalty_snapshot(0, 45),
        }
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._monitor_loop, name="focus-monitor", daemon=True)
        self._thread.start()

    @staticmethod
    def _rule_dict(rule: TargetRule) -> dict:
        return {"kind": rule.kind, "value": rule.value, "match": rule.match}

    def plan_goal(self, goal: str, use_ai: bool = True) -> dict:
        goal = " ".join(str(goal).split())[:300]
        if not goal:
            raise ValueError("请先写下要完成的目标")
        plan = self.parser.plan_goal(goal, use_ai=bool(use_ai))
        config = plan.config
        targets = list(config.allowed_targets + config.blocked_targets)
        converted: list[TargetRule] = list(targets)
        if not converted and config.mode != "blackout":
            converted = list(recommend_targets(goal, self.parser.scenarios))
        config_dict = session_config_to_dict(config)
        if config.mode == "whitelist":
            config_dict["allowed_targets"] = [self._rule_dict(item) for item in converted]
        elif config.mode == "blacklist":
            config_dict["blocked_targets"] = [self._rule_dict(item) for item in converted]
        config_dict["needs_clarification"] = False
        config_dict["clarification_question"] = ""
        scenes = [
            {
                "name": scene.name,
                "description": scene.description,
                "targets": [self._rule_dict(item) for item in scene.targets],
            }
            for scene in group_targets_by_scene(goal, converted)
        ]
        return {
            "goal": goal,
            "source": plan.source,
            "detail": plan.detail,
            "ai_used": plan.ai_used,
            "fallback_reason": plan.fallback_reason,
            "model": plan.model,
            "config": config_dict,
            "scenes": scenes,
        }

    def preview_alert(self) -> dict:
        """Queue a harmless desktop-pet preview without starting monitoring."""
        self.preview_count += 1
        preview_targets = ("Bilibili 视频页面", "微博热搜", "淘宝购物车")
        preview_target = preview_targets[(self.preview_count - 1) % len(preview_targets)]
        line = self.copy_provider.alert_line(
            duration_minutes=45,
            rule_description="预览提醒",
            current_target=preview_target,
            elapsed_seconds=9,
            roast_intensity="mild",
        )
        penalty = penalty_snapshot(min(self.preview_count, 4), 45)
        alert = NativeAlert(
            line=line,
            target_label=preview_target,
            elapsed_seconds=9,
            remaining_seconds=24 * 60 + 36,
            alert_count=self.preview_count,
            cat_name=self._cat_name(),
            cat_skin=self._cat_skin(),
            cat_stage_index=self._cat_stage_index(),
            penalty_points=penalty["penalty_points"],
            focus_score=penalty["focus_score"],
            coins_at_risk=penalty["coins_lost"],
            is_preview=True,
        )
        if self.on_alert:
            self.on_alert(alert)
        return {
            "queued": True,
            "mood": "patient" if self.preview_count <= 2 else "judging",
            "cat_name": alert.cat_name,
        }

    def preview_reaction(self, kind: str) -> dict:
        specs = {
            "shy": ("完成动作", "脸红但嘴硬", "两边腮红已经出卖了它：这轮确实漂亮"),
            "wiggle": ("走神动作", "摇头拒绝这次偏航", "抓到一次偏航，但这次只是动作预览"),
            "angry": ("失败动作", "茶杯先替它翻了", "不扣历史成长，下轮把这口气赢回来"),
        }
        if kind not in specs:
            raise ValueError("没有这种小猫动作")
        title, headline, detail = specs[kind]
        reaction = NativeReaction(
            kind=kind,
            title=title,
            headline=headline,
            detail=detail,
            cat_name=self._cat_name(),
            cat_skin=self._cat_skin(),
            cat_stage_index=self._cat_stage_index(),
        )
        if self.on_reaction:
            self.on_reaction(reaction)
        return {"queued": True, "kind": kind, "cat_name": reaction.cat_name}

    def report_browser_tab(self, payload: dict) -> dict:
        return self.browser_bridge.report(payload)

    def _cat_name(self) -> str:
        profile = getattr(self, "profile", None)
        if profile is None:
            return "Luna"
        return str(profile.snapshot().get("cat_name") or "Luna")

    def _cat_skin(self) -> str:
        profile = getattr(self, "profile", None)
        if profile is None:
            return DEFAULT_CAT_SKIN
        return str(profile.snapshot().get("pet", {}).get("skin") or DEFAULT_CAT_SKIN)

    def _cat_stage_index(self) -> int:
        profile = getattr(self, "profile", None)
        if profile is None:
            return 0
        return int(profile.snapshot().get("pet", {}).get("stage_index") or 0)

    def rename_pet(self, name: str) -> dict:
        with self.lock:
            return self.profile.rename_cat(name)

    def select_pet_skin(self, skin_id: str) -> dict:
        with self.lock:
            return self.profile.set_cat_skin(skin_id)

    def cloud_ai_settings(self) -> dict:
        return self.cloud_settings.snapshot()

    def update_cloud_ai_settings(self, payload: dict) -> dict:
        with self.lock:
            return self.cloud_settings.update(payload)

    def create_custom_pet(
        self,
        name: str,
        image_data: str,
        renderer: str = "local",
        consent: bool = False,
    ) -> dict:
        with self.lock:
            selected = str(renderer or "local").strip()
            if selected == "gemini":
                if not consent:
                    raise ValueError("使用云端卡通化前，需要确认照片将发送给所选模型服务")
                generated = self.cloud_pet_client.cartoonize(image_data)
                return self.profile.create_custom_pet(
                    name,
                    generated,
                    renderer="gemini-image+local-growth-v1",
                )
            if selected != "local":
                raise ValueError("不支持这种宠物生成方式")
            return self.profile.create_custom_pet(name, image_data)

    def delete_custom_pet(self, custom_id: str) -> dict:
        with self.lock:
            return self.profile.delete_custom_pet(custom_id)

    def start_session(self, payload: dict) -> dict:
        goal = " ".join(str(payload.get("goal", "")).split())[:300]
        config_payload = payload.get("config")
        if not isinstance(config_payload, dict):
            raise ValueError("缺少会话配置")
        config_payload = {**config_payload, "needs_clarification": False, "clarification_question": ""}
        config = parse_session_response(json.dumps(config_payload, ensure_ascii=False))
        has_domain_rules = any(
            rule.kind == "domain" for rule in config.allowed_targets + config.blocked_targets
        )
        if has_domain_rules and not self.browser_bridge.status()["connected"]:
            raise ValueError(
                "网址白名单还看不到地址栏：请先加载 browser_extension 浏览器桥接，连接成功后再开始"
            )
        with self.lock:
            if self.engine and self.engine.state in {SessionState.RUNNING, SessionState.PAUSED}:
                raise ValueError("已有一轮专注正在进行")
            self.goal = goal
            if config.mode == "whitelist" and goal and config.allowed_targets:
                self.parser.learn_goal(goal, config.allowed_targets)
            self.engine = FocusSessionEngine(config, own_pid=os.getpid())
            self.dynamic_allowed.clear()
            self.dismissed_suggestions.clear()
            self.suggestions.clear()
            self.notified_suggestions.clear()
            self.soft_until.clear()
            self.last_status = {
                "state": "running",
                "remaining_seconds": config.duration_minutes * 60,
                "total_seconds": config.duration_minutes * 60,
                "violating": False,
                "violation_elapsed_seconds": 0,
                "target_label": "",
                "alert_count": 0,
                "current": "请切换到任务窗口",
                "smart_allow": "",
                "reward": None,
                "penalty": penalty_snapshot(0, config.duration_minutes),
            }
        return self.status()

    def pause(self) -> dict:
        with self.lock:
            if self.engine:
                self.engine.pause()
                self.last_status["state"] = self.engine.state.value
        return self.status()

    def resume(self) -> dict:
        with self.lock:
            if self.engine:
                self.engine.resume()
                self.last_status["state"] = self.engine.state.value
        return self.status()

    def stop_session(self) -> dict:
        reaction = None
        with self.lock:
            if self.engine:
                total = self.engine.config.duration_minutes * 60
                remaining = self.engine.remaining_seconds()
                elapsed_minutes = max(0, round((total - remaining) / 60))
                self.profile.record_aborted(elapsed_minutes, self.goal)
                self.engine.stop()
                self.last_status["state"] = "stopped"
                self.last_status["remaining_seconds"] = remaining
                self.engine = None
                if elapsed_minutes > 0:
                    reaction = NativeReaction(
                        kind="angry",
                        title="本轮提前结束",
                        headline=f"{self._cat_name()}把茶杯推翻了",
                        detail="不扣历史成长，下轮把这口气赢回来",
                        cat_name=self._cat_name(),
                        cat_skin=self._cat_skin(),
                        cat_stage_index=self._cat_stage_index(),
                    )
        if reaction and self.on_reaction:
            self.on_reaction(reaction)
        return self.status()

    def approve_suggestion(self, suggestion_id: str, remember: bool = False) -> dict:
        with self.lock:
            suggestion = self.suggestions.pop(suggestion_id, None)
            if not suggestion:
                raise ValueError("这条推荐已经失效")
            self.dynamic_allowed.add(suggestion.process_name.casefold())
            self.soft_until.pop(suggestion_id, None)
            self.notified_suggestions.discard(suggestion_id)
            if remember:
                self.relations.remember(suggestion)
        return self.status()

    def dismiss_suggestion(self, suggestion_id: str) -> dict:
        with self.lock:
            self.suggestions.pop(suggestion_id, None)
            self.soft_until.pop(suggestion_id, None)
            self.notified_suggestions.discard(suggestion_id)
            self.dismissed_suggestions.add(suggestion_id)
        return self.status()

    def status(self) -> dict:
        with self.lock:
            now = time.monotonic()
            suggestions = []
            for suggestion_id, suggestion in self.suggestions.items():
                item = suggestion.to_dict()
                item["soft_remaining_seconds"] = max(0, round(self.soft_until.get(suggestion_id, now) - now))
                suggestions.append(item)
            return {
                **self.last_status,
                "goal": self.goal,
                "suggestions": suggestions,
                "profile": self.profile.snapshot(),
                "relation_database": self.relations.stats(),
                "goal_scenario_database": self.parser.scenario_stats(),
                "ai_planner": self.parser.ai_status(),
                "cloud_ai": self.cloud_settings.snapshot(),
                "roast_database": self.copy_provider.stats(),
                "browser_bridge": {
                    **self.browser_bridge.status(now),
                    "extension_path": str(browser_extension_root()),
                },
            }

    def return_to_focus(self) -> bool:
        with self.lock:
            hwnd = self.last_compliant_hwnd
        return activate_window(hwnd) if hwnd else False

    def _related_snapshot(
        self, config: SessionConfig, snapshot: ForegroundSnapshot, now: float
    ) -> tuple[ForegroundSnapshot, str, NativeSuggestion | None]:
        if config.mode != "whitelist":
            return snapshot, "", None
        local_domain = str(snapshot.browser_domain or "").casefold().rstrip(".")
        is_control_page = (
            local_domain in {"127.0.0.1", "localhost"}
            and "focus buddy" in str(snapshot.window_title or "").casefold()
        )
        if is_control_page:
            compliant = ForegroundSnapshot(
                snapshot.hwnd,
                os.getpid(),
                snapshot.process_name,
                snapshot.window_title,
                snapshot.input_idle_seconds,
                snapshot.browser_domain,
            )
            return compliant, "Focus Buddy 控制台 · 自动放行", None
        matches = matching_rules(config.allowed_targets, snapshot)
        if matches:
            domain_match = next((rule for rule in matches if rule.kind == "domain"), None)
            status = f"网址已放行 · {snapshot.browser_domain}" if domain_match else ""
            return snapshot, status, None
        if browser_domain_is_unknown(config, snapshot):
            # A missing/stale extension heartbeat is an unknown state, not proof
            # of distraction. Mark this tick compliant so it can never deduct.
            compliant = ForegroundSnapshot(
                snapshot.hwnd,
                os.getpid(),
                snapshot.process_name,
                snapshot.window_title,
                snapshot.input_idle_seconds,
                snapshot.browser_domain,
            )
            return compliant, "网址识别暂时断开 · 本轮不扣分", None
        process = Path(snapshot.process_name).name.casefold()
        if process in self.dynamic_allowed:
            compliant = ForegroundSnapshot(
                snapshot.hwnd, os.getpid(), snapshot.process_name,
                snapshot.window_title, snapshot.input_idle_seconds
            )
            return compliant, "本轮已允许", None
        suggestion = self.relations.suggest(config.allowed_targets, snapshot)
        if not suggestion:
            return snapshot, "", None
        if self.relations.is_remembered(suggestion):
            self.dynamic_allowed.add(process)
            compliant = ForegroundSnapshot(
                snapshot.hwnd, os.getpid(), snapshot.process_name,
                snapshot.window_title, snapshot.input_idle_seconds
            )
            return compliant, "已学习的关联工具", None
        if suggestion.suggestion_id in self.dismissed_suggestions:
            return snapshot, "", None
        self.suggestions[suggestion.suggestion_id] = suggestion
        deadline = self.soft_until.setdefault(
            suggestion.suggestion_id, now + suggestion.soft_grace_seconds
        )
        first_seen = deadline - suggestion.soft_grace_seconds
        native_suggestion = None
        if (
            now - first_seen >= 4
            and suggestion.suggestion_id not in self.notified_suggestions
        ):
            self.notified_suggestions.add(suggestion.suggestion_id)
            native_suggestion = NativeSuggestion(
                suggestion_id=suggestion.suggestion_id,
                label=suggestion.label,
                reason=suggestion.reason,
                soft_remaining_seconds=max(0, round(deadline - now)),
                cat_name=self._cat_name(),
                cat_skin=self._cat_skin(),
                cat_stage_index=self._cat_stage_index(),
            )
        if now <= deadline:
            compliant = ForegroundSnapshot(
                snapshot.hwnd, os.getpid(), snapshot.process_name,
                snapshot.window_title, snapshot.input_idle_seconds
            )
            return compliant, f"智能缓冲 · {suggestion.label}", native_suggestion
        return snapshot, "推荐待确认", native_suggestion

    def _monitor_loop(self) -> None:
        while not self._stop_event.wait(0.5):
            try:
                snapshot = get_foreground_snapshot()
                snapshot = self.browser_bridge.enrich(snapshot)
            except Exception:
                continue
            alert_payload: NativeAlert | None = None
            suggestion_payload: NativeSuggestion | None = None
            reaction_payload: NativeReaction | None = None
            with self.lock:
                self.last_snapshot = snapshot
                engine = self.engine
                if not engine:
                    continue
                now = time.monotonic()
                effective, smart_allow, suggestion_payload = self._related_snapshot(
                    engine.config, snapshot, now
                )
                update = engine.tick(effective, now=now)
                penalty = penalty_snapshot(engine.alert_count, engine.config.duration_minutes)
                self.last_status.update(
                    {
                        "state": update.state.value,
                        "remaining_seconds": update.remaining_seconds,
                        "violating": update.violating,
                        "violation_elapsed_seconds": update.violation_elapsed_seconds,
                        "target_label": update.target_label,
                        "alert_count": engine.alert_count,
                        "current": snapshot.local_label,
                        "smart_allow": smart_allow,
                        "penalty": penalty,
                    }
                )
                if not update.violating and snapshot.pid != os.getpid():
                    self.last_compliant_hwnd = snapshot.hwnd
                if update.alert:
                    line = self.copy_provider.alert_line(
                        duration_minutes=engine.config.duration_minutes,
                        rule_description="专注白名单",
                        current_target=update.alert.target_label,
                        elapsed_seconds=update.alert.elapsed_seconds,
                        roast_intensity=engine.config.roast_intensity,
                    )
                    alert_payload = NativeAlert(
                        line=line,
                        target_label=update.alert.target_label,
                        elapsed_seconds=update.alert.elapsed_seconds,
                        remaining_seconds=update.alert.remaining_seconds,
                        alert_count=engine.alert_count,
                        cat_name=self._cat_name(),
                        cat_skin=self._cat_skin(),
                        cat_stage_index=self._cat_stage_index(),
                        penalty_points=penalty["penalty_points"],
                        focus_score=penalty["focus_score"],
                        coins_at_risk=penalty["coins_lost"],
                    )
                if update.just_completed:
                    reward = self.profile.record_completion(
                        engine.config.duration_minutes, engine.alert_count, self.goal
                    )
                    self.last_status["reward"] = reward
                    reaction_payload = NativeReaction(
                        kind="shy",
                        title="专注完成 · 猫粮到账",
                        headline=f"{reward['pet_name']}偷偷替你骄傲",
                        detail=f"清醒值 {reward['focus_score']} · +{reward['coins']} 猫币 · 成长 {reward['care_minutes']} 分钟",
                        cat_name=reward["pet_name"],
                        cat_skin=self._cat_skin(),
                        cat_stage_index=self._cat_stage_index(),
                    )
                    self.engine = None
            if alert_payload and self.on_alert:
                self.on_alert(alert_payload)
            if suggestion_payload and self.on_suggestion:
                self.on_suggestion(suggestion_payload)
            if reaction_payload and self.on_reaction:
                self.on_reaction(reaction_payload)

    def close(self) -> None:
        self._stop_event.set()
        with self.lock:
            if self.engine:
                self.engine.stop()
        self.copy_provider.close()
