"""Model-facing services kept outside the deterministic monitoring loop."""

from __future__ import annotations

import os
import random
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace

from .ai_planner import build_ai_planning_messages, parse_ai_planning_result
from .contracts import (
    SessionConfig,
    TargetRule,
    parse_session_response,
    sanitize_roast_response,
    sanitize_summary_response,
)
from .copy_library import FALLBACK_PHRASES, SUMMARY_FALLBACK_PHRASES
from .cloud_ai import CloudAISettingsStore, OpenRouterClient
from .goal_scenarios import GoalScenarioStore
from .ollama_client import OllamaClient
from .recommendations import fallback_config_for_goal
from .roast_database import RoastDatabase
from .prompts import (
    build_clarification_followup_messages,
    build_roast_messages,
    build_session_parse_messages,
    build_session_summary_messages,
)


@dataclass(frozen=True)
class GoalPlan:
    config: SessionConfig
    source: str
    detail: str = ""
    ai_used: bool = False
    fallback_reason: str = ""
    model: str = ""


class SessionParserService:
    def __init__(
        self,
        client: OllamaClient,
        model: str = "qwen3.5:9b",
        *,
        cloud_settings: CloudAISettingsStore | None = None,
        cloud_client: OpenRouterClient | None = None,
    ):
        self.client = client
        self.cloud_settings = cloud_settings
        self.cloud_client = cloud_client
        self.model = os.environ.get("FOCUS_BUDDY_MODEL", "").strip() or model
        try:
            self.ai_timeout_seconds = max(
                10.0,
                min(180.0, float(os.environ.get("FOCUS_BUDDY_AI_TIMEOUT", "60"))),
            )
        except ValueError:
            self.ai_timeout_seconds = 60.0
        self.scenarios = GoalScenarioStore()
        self._ai_status = {
            "enabled": True,
            "state": "not_checked",
            "online": False,
            "model": self.model,
            "last_source": "",
            "last_error": "",
            "last_latency_ms": 0,
        }

    def parse(self, user_input: str) -> SessionConfig:
        raw = self.client.chat(
            model=self.model,
            messages=build_session_parse_messages(user_input),
            temperature=0.1,
        )
        return parse_session_response(raw)

    @staticmethod
    def _deduplicate(targets: tuple[TargetRule, ...]) -> tuple[TargetRule, ...]:
        seen: set[tuple[str, str, str]] = set()
        result: list[TargetRule] = []
        for target in targets:
            key = (target.kind, target.value.casefold(), target.match)
            if key not in seen:
                seen.add(key)
                result.append(target)
        return tuple(result)

    def _local_plan(self, goal: str, fallback_reason: str = "") -> GoalPlan:
        source = "本地场景库 · AI回退" if fallback_reason else "本地场景库 · 即时规划"
        self._ai_status.update(
            {
                "state": "fallback" if fallback_reason else "local",
                "last_source": source,
                "last_error": fallback_reason,
            }
        )
        return GoalPlan(
            fallback_config_for_goal(goal, self.scenarios),
            source,
            detail="使用本地场景数据库完成规划",
            fallback_reason=fallback_reason,
            model=self.model,
        )

    @staticmethod
    def _negative_mode_is_explicit(goal: str) -> bool:
        compact = goal.replace(" ", "")
        return any(word in compact for word in ("禁止", "不要", "不能", "别打开", "避开"))

    def _available_model(self) -> str:
        status_method = getattr(self.client, "status", None)
        if not callable(status_method):
            return self.model
        status = status_method()
        self._ai_status["online"] = bool(status.online)
        if not status.online:
            raise RuntimeError("本机Ollama未启动")
        models = tuple(str(item) for item in status.models if str(item))
        if self.model in models:
            return self.model
        preferred = next(
            (
                item for item in models
                if any(family in item.casefold() for family in ("qwen", "llama", "gemma", "mistral"))
            ),
            "",
        )
        if preferred:
            return preferred
        raise RuntimeError(f"没有可用的对话模型，请先下载 {self.model}")

    def plan_goal(self, goal: str, use_ai: bool = True) -> GoalPlan:
        """Use the selected AI provider and fall back to the validated local DB."""
        if not use_ai:
            self._ai_status["enabled"] = False
            return self._local_plan(goal)
        provider = (
            self.cloud_settings.snapshot()["text_provider"]
            if self.cloud_settings is not None
            else "ollama"
        )
        if provider == "local":
            self._ai_status["enabled"] = False
            return self._local_plan(goal)
        self._ai_status.update({"enabled": True, "state": "thinking", "last_error": ""})
        started = time.perf_counter()
        try:
            if provider == "openrouter":
                if self.cloud_client is None or self.cloud_settings is None:
                    raise ValueError("OpenRouter连接尚未初始化")
                model = self.cloud_settings.snapshot()["openrouter_model"]
                raw = self.cloud_client.chat(
                    model=model,
                    messages=build_ai_planning_messages(goal, self.scenarios.catalog()),
                    temperature=0.1,
                    max_context=4096,
                    timeout_seconds=self.ai_timeout_seconds,
                )
                source_prefix = "云端AI"
            else:
                model = self._available_model()
                raw = self.client.chat(
                    model=model,
                    messages=build_ai_planning_messages(goal, self.scenarios.catalog()),
                    temperature=0.1,
                    max_context=4096,
                    timeout_seconds=self.ai_timeout_seconds,
                )
                source_prefix = "本机AI"
            result = parse_ai_planning_result(
                raw,
                goal=goal,
                valid_scene_ids={str(item["id"]) for item in self.scenarios.scenarios},
            )
            local = fallback_config_for_goal(goal, self.scenarios)
            mode = result.mode
            if mode == "blackout" and local.mode != "blackout":
                mode = "whitelist"
            if mode == "blacklist" and not self._negative_mode_is_explicit(goal):
                mode = "whitelist"

            if mode == "blackout":
                allowed: tuple[TargetRule, ...] = ()
                blocked: tuple[TargetRule, ...] = ()
            elif mode == "blacklist":
                if not result.explicit_targets:
                    raise ValueError("AI黑名单没有明确目标")
                allowed = ()
                blocked = self._deduplicate(result.explicit_targets)[:10]
            else:
                mode = "whitelist"
                learned = self.scenarios.learned_targets(goal)
                scene_targets = self.scenarios.targets_for_ids(result.scene_ids)
                local_matches = self.scenarios.match(goal)
                local_targets = local.allowed_targets if local_matches else ()
                allowed = self._deduplicate(
                    learned
                    + scene_targets
                    + result.explicit_targets
                    + local_targets
                )[:12]
                if not allowed:
                    raise ValueError("AI没有给出可执行的软件场景")
                blocked = ()

            config = replace(
                local,
                duration_minutes=result.duration_minutes,
                mode=mode,
                allowed_targets=allowed,
                blocked_targets=blocked,
                needs_clarification=False,
                clarification_question="",
            )
            latency_ms = round((time.perf_counter() - started) * 1000)
            source = f"{source_prefix} · {model}"
            self._ai_status.update(
                {
                    "state": "ready",
                    "online": True,
                    "model": model,
                    "last_source": source,
                    "last_error": "",
                    "last_latency_ms": latency_ms,
                }
            )
            return GoalPlan(
                config,
                source,
                detail=result.reason,
                ai_used=True,
                model=model,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self._ai_status["last_latency_ms"] = round((time.perf_counter() - started) * 1000)
            return self._local_plan(goal, str(exc)[:120])

    def learn_goal(self, goal: str, targets: tuple[TargetRule, ...]) -> None:
        """Remember the whitelist the user actually chose for a similar goal."""
        self.scenarios.learn(goal, tuple(targets))

    def scenario_stats(self) -> dict:
        return self.scenarios.stats()

    def ai_status(self) -> dict:
        return dict(self._ai_status)

    def parse_followup(
        self,
        *,
        original_input: str,
        clarification_question: str,
        clarification_answer: str,
    ) -> SessionConfig:
        raw = self.client.chat(
            model=self.model,
            messages=build_clarification_followup_messages(
                original_input=original_input,
                clarification_question=clarification_question,
                clarification_answer=clarification_answer,
            ),
            temperature=0.1,
        )
        return parse_session_response(raw)


class CopyProvider:
    """Return local copy instantly and prepare optional model copy in background."""

    def __init__(
        self,
        client: OllamaClient,
        model: str = "qwen3.5:9b",
        model_probability: float = 0.3,
        roast_database: RoastDatabase | None = None,
    ):
        self.client = client
        self.model = model
        self.model_probability = max(0.0, min(1.0, model_probability))
        self.roasts = roast_database or RoastDatabase()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="focus-copy")
        self._lock = threading.Lock()
        self._pending: set[tuple[str, str]] = set()
        self._prepared: dict[tuple[str, str], str] = {}

    def alert_line(
        self,
        *,
        duration_minutes: int,
        rule_description: str,
        current_target: str,
        elapsed_seconds: int,
        roast_intensity: str,
    ) -> str:
        intensity = roast_intensity if roast_intensity in FALLBACK_PHRASES else "mild"
        key = (intensity, current_target)
        with self._lock:
            prepared = self._prepared.pop(key, None)
        line = prepared
        if line is None:
            try:
                line = self.roasts.pick(current_target, intensity)
            except (OSError, RuntimeError, sqlite3.Error):
                line = None
        line = line or random.choice(FALLBACK_PHRASES[intensity])
        self.prepare_alert(
            duration_minutes=duration_minutes,
            rule_description=rule_description,
            current_target=current_target,
            elapsed_seconds=elapsed_seconds,
            roast_intensity=intensity,
        )
        return line

    def prepare_alert(
        self,
        *,
        duration_minutes: int,
        rule_description: str,
        current_target: str,
        elapsed_seconds: int,
        roast_intensity: str,
    ) -> None:
        if random.random() > self.model_probability:
            return
        key = (roast_intensity, current_target)
        with self._lock:
            if key in self._pending or key in self._prepared:
                return
            self._pending.add(key)
        self._executor.submit(
            self._generate_alert,
            key,
            duration_minutes,
            rule_description,
            current_target,
            elapsed_seconds,
            roast_intensity,
        )

    def _generate_alert(
        self,
        key: tuple[str, str],
        duration_minutes: int,
        rule_description: str,
        current_target: str,
        elapsed_seconds: int,
        roast_intensity: str,
    ) -> None:
        try:
            raw = self.client.chat(
                model=self.model,
                messages=build_roast_messages(
                    duration_minutes=duration_minutes,
                    rule_description=rule_description,
                    current_target=current_target,
                    elapsed_seconds=elapsed_seconds,
                    roast_intensity=roast_intensity,
                ),
                temperature=0.55,
                max_context=4096,
            )
            safe = sanitize_roast_response(raw)
            if safe:
                try:
                    self.roasts.add_generated(safe, current_target, roast_intensity)
                except (OSError, RuntimeError, sqlite3.Error):
                    pass
                with self._lock:
                    self._prepared[key] = safe
        except (RuntimeError, ValueError):
            pass
        finally:
            with self._lock:
                self._pending.discard(key)

    def local_summary(self, alert_count: int, max_alerts: int) -> str:
        category = "steady" if alert_count <= max(1, max_alerts // 5) else "recovered"
        return random.choice(SUMMARY_FALLBACK_PHRASES[category])

    def stats(self) -> dict:
        try:
            return self.roasts.stats()
        except (OSError, RuntimeError, sqlite3.Error):
            return {"line_count": 0, "category_count": 0, "generated_count": 0, "used_count": 0}

    def generate_summary(self, duration_minutes: int, alert_count: int, max_alerts: int) -> str | None:
        try:
            raw = self.client.chat(
                model=self.model,
                messages=build_session_summary_messages(
                    duration_minutes=duration_minutes,
                    alert_count=alert_count,
                    max_alerts=max_alerts,
                ),
                temperature=0.45,
                max_context=4096,
            )
            return sanitize_summary_response(raw)
        except (RuntimeError, ValueError):
            return None

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
