"""Transparent desktop-pet alerts driven by one coherent cat cutout."""

from __future__ import annotations

import math
import time
import tkinter as tk
from typing import Callable

from .cat_skins import cat_reaction_asset_path, normalize_cat_skin
from .controller import NativeAlert, NativeReaction, NativeSuggestion


class CatAlertWindow:
    """Let the cat enter first, react, then reveal a compact speech bubble."""

    WIDTH = 980
    HEIGHT = 410
    KEY_COLOR = "#010203"
    BUBBLE = "#151923"
    INK = "#f8f6f1"
    MUTED = "#a7adbb"
    CORAL = "#ff667d"
    LIME = "#d4f66c"

    def __init__(self, root: tk.Tk, on_return: Callable[[], object] | None = None):
        self.root = root
        self.on_return = on_return
        self.window: tk.Toplevel | None = None
        self.cat_image: tk.PhotoImage | None = None
        # Compatibility alias kept for callers that inspect whether an alert
        # visual loaded. Motion now comes from continuous canvas movement,
        # never from morphing between inconsistent generated poses.
        self.walk_frames: list[tk.PhotoImage] = []
        self._image_cache: dict[str, tk.PhotoImage] = {}
        self._callbacks: dict[str, Callable[[], object]] = {}
        self._cat_age = "young"
        self._activate_skin("tuxedo", 0)

    def _activate_skin(
        self,
        skin_id: str,
        stage_index: int = 0,
        action: str = "idle",
    ) -> None:
        skin_id = normalize_cat_skin(skin_id)
        age = "young" if int(stage_index) <= 1 else "grown"
        self._cat_age = age
        cache_key = f"{skin_id}:{age}:{action}"
        try:
            image = self._image_cache.get(cache_key)
            if image is None:
                image = tk.PhotoImage(
                    file=str(cat_reaction_asset_path(skin_id, action, stage_index))
                )
                self._image_cache[cache_key] = image
            self.cat_image = image
            self.walk_frames = [self.cat_image]
        except tk.TclError:
            self.cat_image = None
            self.walk_frames = []

    def show(self, alert: NativeAlert) -> None:
        mood = "wiggle" if alert.alert_count <= 2 else "angry"
        self._activate_skin(alert.cat_skin, alert.cat_stage_index, mood)
        title = f"第 {alert.alert_count} 次偏航 · 已记账"
        detail = (
            f"在 {alert.target_label} 停留 {alert.elapsed_seconds}s"
            f"  ·  本轮还剩 {self._clock(alert.remaining_seconds)}"
        )
        penalty_label = (
            f"预览模式 · 正式触发时清醒值降至 {alert.focus_score}"
            if alert.is_preview
            else f"本轮代价  清醒值 {alert.focus_score}/100 · 预计少 {alert.coins_at_risk} 猫币"
        )
        self._show_scene(
            mood=mood,
            title=title,
            headline=alert.line,
            detail=detail,
            penalty_label=penalty_label,
            actions=(
                ("带我回去", "return", True),
                ("我自己回", "dismiss", False),
            ),
            callbacks={"return": self._return, "dismiss": self.close},
            lifetime_ms=13000,
        )

    def show_suggestion(
        self,
        suggestion: NativeSuggestion,
        on_once: Callable[[], object],
        on_remember: Callable[[], object],
        on_dismiss: Callable[[], object],
    ) -> None:
        self._activate_skin(suggestion.cat_skin, suggestion.cat_stage_index, "idle")
        self._show_scene(
            mood="curious",
            title=f"{suggestion.cat_name}闻到了任务的味道",
            headline=f"{suggestion.label}，是队友吗？",
            detail=f"{suggestion.reason}  ·  已给 {suggestion.soft_remaining_seconds}s 缓冲",
            penalty_label="智能缓冲中 · 现在不会扣清醒值",
            actions=(
                ("本轮放行", "once", True),
                ("记住它", "remember", False),
                ("不是队友", "dismiss", False),
            ),
            callbacks={"once": on_once, "remember": on_remember, "dismiss": on_dismiss},
            lifetime_ms=18000,
        )

    def show_reaction(self, reaction: NativeReaction) -> None:
        action = "happy" if reaction.kind == "shy" else reaction.kind
        self._activate_skin(reaction.cat_skin, reaction.cat_stage_index, action)
        labels = {
            "shy": "奖励已结算 · 历史成长永久保留",
            "wiggle": "偏航动作预览 · 不实际扣猫币",
            "angry": "本轮停止 · 不扣历史成长",
        }
        self._show_scene(
            mood=reaction.kind,
            title=reaction.title,
            headline=reaction.headline,
            detail=reaction.detail,
            penalty_label=labels.get(reaction.kind, "小猫动作"),
            actions=(("知道啦", "dismiss", True),),
            callbacks={"dismiss": self.close},
            lifetime_ms=9000,
        )

    def _show_scene(
        self,
        *,
        mood: str,
        title: str,
        headline: str,
        detail: str,
        penalty_label: str,
        actions: tuple[tuple[str, str, bool], ...],
        callbacks: dict[str, Callable[[], object]],
        lifetime_ms: int,
    ) -> None:
        self.close()
        window = tk.Toplevel(self.root)
        self.window = window
        window.overrideredirect(True)
        window.configure(bg=self.KEY_COLOR)
        window.attributes("-topmost", True)
        try:
            # Windows treats only the unused canvas color as transparent. The
            # cat and speech bubble remain fully opaque with no card around them.
            window.attributes("-transparentcolor", self.KEY_COLOR)
        except tk.TclError:
            pass

        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        # The companion is an event near the user's visual focus, not a fixed
        # notification imprisoned in the bottom-right corner.
        x = max(12, (screen_width - self.WIDTH) // 2)
        y = max(24, min(screen_height - self.HEIGHT - 34, int(screen_height * .56)))
        window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        canvas = tk.Canvas(
            window,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg=self.KEY_COLOR,
            highlightthickness=0,
            borderwidth=0,
        )
        canvas.pack(fill="both", expand=True)
        self._callbacks = callbacks
        for tag in (*callbacks, "close"):
            canvas.tag_bind(tag, "<Button-1>", lambda _event, name=tag: self._trigger(name))
            canvas.tag_bind(tag, "<Enter>", lambda _event: canvas.configure(cursor="hand2"))
            canvas.tag_bind(tag, "<Leave>", lambda _event: canvas.configure(cursor=""))
        window.bind("<Escape>", lambda _event: self._trigger("dismiss"))
        window.deiconify()
        window.update_idletasks()
        window.lift()
        try:
            window.focus_force()
        except tk.TclError:
            pass
        window.after_idle(lambda: window.lift() if self.window is window else None)

        started = time.monotonic()
        self._animate_scene(
            window, canvas, started, mood, title, headline, detail, penalty_label, actions
        )
        window.after(lifetime_ms, lambda: self._trigger("dismiss") if self.window is window else None)

    def _animate_scene(
        self,
        window: tk.Toplevel,
        canvas: tk.Canvas,
        started: float,
        mood: str,
        title: str,
        headline: str,
        detail: str,
        penalty_label: str,
        actions: tuple[tuple[str, str, bool], ...],
    ) -> None:
        try:
            if self.window is not window or not window.winfo_exists():
                return
            elapsed = time.monotonic() - started
            arrival = .82 if mood == "angry" else 1.02
            travel = min(1.0, elapsed / arrival)
            eased = 1 - (1 - travel) ** 4
            stopped = max(0.0, elapsed - arrival)
            # 560px-wide cutouts fit fully at x=694; the old x=775 position
            # clipped the rightmost 75px, most visibly at the tail tip.
            target_x = 694
            cat_x = self.WIDTH + 340 + (target_x - self.WIDTH - 340) * eased
            cat_y = 245 + math.sin(elapsed * 2.35) * (1.8 if travel >= 1 else 3.2)
            if mood == "angry" and stopped < 2.2:
                reach = min(1.0, stopped / .72)
                cat_x += math.sin(reach * math.pi) * 12
                cat_y += math.sin(reach * math.pi) * 2
            elif mood == "wiggle" and stopped < 3.2:
                cat_x += math.sin(stopped * 7.2) * 3.5
            elif mood == "shy" and stopped < 3.2:
                cat_y += abs(math.sin(stopped * 4.8)) * 7
            elif mood == "curious":
                cat_y -= 3.5 * (0.5 + 0.5 * math.sin(stopped * 2.8))

            canvas.delete("all")
            if elapsed > arrival + .18:
                bubble_progress = min(1.0, (elapsed - arrival - .18) / .34)
                self._draw_bubble(
                    canvas,
                    1 - (1 - bubble_progress) ** 3,
                    title,
                    headline,
                    detail,
                    penalty_label,
                    actions,
                )

            # A small grounded shadow is the only visual below the cutout.
            shadow_scale = .72 + .28 * travel
            canvas.create_oval(
                cat_x - 205 * shadow_scale,
                373,
                cat_x + 205 * shadow_scale,
                397,
                fill="#090b10",
                outline="",
            )

            if self.cat_image:
                canvas.create_image(cat_x, cat_y, image=self.cat_image, anchor="center")
            else:
                canvas.create_text(cat_x, cat_y, text="🐈", fill="white", font=("Segoe UI Emoji", 92))

            face_y = cat_y if self._cat_age == "young" else cat_y - 76
            face_x = cat_x + (16 if self._cat_age == "young" else 30)
            if travel >= 1 and mood == "shy":
                lift = abs(math.sin(stopped * 3.4)) * 8
                blush = 4 + 2 * (0.5 + 0.5 * math.sin(stopped * 5.5))
                canvas.create_oval(
                    face_x - 55 - blush,
                    face_y + 15 - blush / 2,
                    face_x - 31 + blush,
                    face_y + 25 + blush / 2,
                    fill="#ff789b",
                    outline="",
                )
                canvas.create_oval(
                    face_x + 26 - blush,
                    face_y + 15 - blush / 2,
                    face_x + 50 + blush,
                    face_y + 25 + blush / 2,
                    fill="#ff789b",
                    outline="",
                )
                canvas.create_text(cat_x + 18, 82 - lift, text="♥  ♥", fill="#ff9eb1", font=("Segoe UI Symbol", 22, "bold"))
            elif travel >= 1 and mood == "angry":
                cup_phase = min(1.0, max(0.0, (stopped - .12) / 1.05))
                eased_cup = 1 - (1 - cup_phase) ** 3
                cup_x = cat_x + 164 + eased_cup * 52
                cup_y = 307 + eased_cup * 45
                canvas.create_line(
                    cat_x + 76,
                    290,
                    cat_x + 142 + eased_cup * 20,
                    304 + eased_cup * 8,
                    fill="#d4f66c",
                    width=5,
                    smooth=True,
                )
                canvas.create_text(
                    cup_x,
                    cup_y,
                    text="☕",
                    fill="#fff9e8",
                    font=("Segoe UI Emoji", 42),
                    angle=-92 * eased_cup,
                )
                if cup_phase > .42:
                    drop = (cup_phase - .42) / .58
                    canvas.create_oval(
                        cup_x - 22 + drop * 18,
                        cup_y + 13 + drop * 18,
                        cup_x - 13 + drop * 18,
                        cup_y + 24 + drop * 18,
                        fill="#b77c55",
                        outline="",
                    )
            elif travel >= 1 and mood == "wiggle":
                sway = math.sin(stopped * 7.2) * 6
                canvas.create_text(face_x - 74 + sway, face_y - 56, text="⌇", fill=self.LIME, font=("Microsoft YaHei UI", 25, "bold"), angle=-18)
                canvas.create_text(face_x + 70 + sway, face_y - 56, text="⌇", fill=self.LIME, font=("Microsoft YaHei UI", 25, "bold"), angle=18)

            window.after(
                24,
                self._animate_scene,
                window,
                canvas,
                started,
                mood,
                title,
                headline,
                detail,
                penalty_label,
                actions,
            )
        except tk.TclError:
            pass

    def _draw_bubble(
        self,
        canvas: tk.Canvas,
        progress: float,
        title: str,
        headline: str,
        detail: str,
        penalty_label: str,
        actions: tuple[tuple[str, str, bool], ...],
    ) -> None:
        x2, center_y = 646, 205
        width, height = 600 * progress, 286 * progress
        x1, y1, y2 = x2 - width, center_y - height / 2, center_y + height / 2
        if width < 16 or height < 16:
            return
        self._round_rect(canvas, x1 + 9, y1 + 12, x2 + 9, y2 + 12, 34, "#080a0f")
        self._round_rect(canvas, x1 - 2, y1 - 2, x2 + 2, y2 + 2, 34, "#343a49")
        self._round_rect(canvas, x1, y1, x2, y2, 32, self.BUBBLE)
        canvas.create_polygon(
            x2 - 3, center_y - 18, x2 + 34, center_y + 2, x2 - 3, center_y + 22,
            fill=self.BUBBLE, outline="",
        )
        if progress < .86:
            return
        canvas.create_text(
            58, 92, text=title, anchor="w", fill=self.CORAL,
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        self._round_rect(canvas, 360, 76, 614, 110, 17, "#272c38")
        canvas.create_text(
            487, 93, text=penalty_label, anchor="center", fill=self.LIME,
            font=("Microsoft YaHei UI", 9, "bold"), width=238,
        )
        canvas.create_text(
            58, 140, text=headline, anchor="w", fill=self.INK,
            font=("Microsoft YaHei UI", 24, "bold"), width=535,
        )
        canvas.create_text(
            58, 186, text=detail, anchor="w", fill=self.MUTED,
            font=("Microsoft YaHei UI", 11), width=535,
        )
        canvas.create_line(58, 218, 610, 218, fill="#2c3240", width=1)
        canvas.create_text(
            58, 238, text="惩罚只作用于本轮未结算奖励，不会扣历史成长。",
            anchor="w", fill="#7f8798", font=("Microsoft YaHei UI", 9),
        )
        canvas.create_text(
            618, 90, text="×", tags=("close",), fill="#858c9b",
            font=("Segoe UI", 15),
        )
        cursor_x = 58
        for label, tag, primary in actions:
            button_width = max(86, 28 + len(label) * 14)
            fill = self.LIME if primary else "#252a35"
            color = "#151710" if primary else "#d5d8e0"
            self._round_rect(canvas, cursor_x, 270, cursor_x + button_width, 313, 20, fill, tags=(tag,))
            canvas.create_text(
                cursor_x + button_width / 2, 291, text=label, tags=(tag,), fill=color,
                font=("Microsoft YaHei UI", 10, "bold"),
            )
            cursor_x += button_width + 9

    @staticmethod
    def _round_rect(
        canvas: tk.Canvas,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        radius: float,
        fill: str,
        tags: tuple[str, ...] = (),
    ) -> int:
        points = (
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        )
        return canvas.create_polygon(
            points, smooth=True, splinesteps=30, fill=fill, outline="", tags=tags
        )

    def _trigger(self, name: str) -> None:
        if name == "close":
            name = "dismiss"
        callback = self._callbacks.get(name)
        self.close()
        if callback:
            callback()

    @staticmethod
    def _clock(seconds: int) -> str:
        minutes, remainder = divmod(max(0, int(seconds)), 60)
        return f"{minutes:02d}:{remainder:02d}"

    def _return(self) -> None:
        self.close()
        if self.on_return:
            self.on_return()

    def close(self) -> None:
        try:
            if self.window and self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass
        self.window = None
        self._callbacks = {}
