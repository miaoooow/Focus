"""Local, privacy-preserving custom pet image generation and storage."""

from __future__ import annotations

import base64
import binascii
import io
import json
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .paths import user_data_root


CUSTOM_PREFIX = "custom:"
CUSTOM_ID_PATTERN = re.compile(r"^[a-f0-9]{16}$")
STAGE_FILES = ("baby.png", "young.png", "adult.png", "guardian.png")
ACTION_FILES = {
    "idle": "idle.png",
    "happy": "happy.png",
    "wiggle": "wiggle.png",
    "angry": "angry.png",
}
MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_IMAGE_SIDE = 6000


def custom_pet_id_from_skin(skin_id: str | None) -> str | None:
    value = str(skin_id or "").strip().casefold()
    if not value.startswith(CUSTOM_PREFIX):
        return None
    custom_id = value.removeprefix(CUSTOM_PREFIX)
    return custom_id if CUSTOM_ID_PATTERN.fullmatch(custom_id) else None


def custom_pet_asset_path(
    custom_id: str,
    stage_index: int,
    root: Path | None = None,
) -> Path:
    if not CUSTOM_ID_PATTERN.fullmatch(str(custom_id)):
        raise ValueError("自定义宠物编号不合法")
    stages = ("baby.png", "young.png", "adult.png", "guardian.png")
    stage_file = stages[min(3, max(0, int(stage_index)))]
    return (root or user_data_root() / "custom_pets") / custom_id / stage_file


def custom_pet_action_path(
    custom_id: str,
    action: str,
    root: Path | None = None,
) -> Path:
    if not CUSTOM_ID_PATTERN.fullmatch(str(custom_id)):
        raise ValueError("自定义宠物编号不合法")
    normalized = str(action or "idle").strip().casefold()
    filename = ACTION_FILES.get(normalized, ACTION_FILES["idle"])
    return (root or user_data_root() / "custom_pets") / custom_id / filename


def custom_pet_exists(custom_id: str, root: Path | None = None) -> bool:
    try:
        return custom_pet_asset_path(custom_id, 0, root).is_file()
    except ValueError:
        return False


class CustomPetStore:
    """Create and manage user-owned pet variants without uploading photos."""

    def __init__(self, root: Path | None = None):
        self.root = root or user_data_root() / "custom_pets"
        self.index_path = self.root / "index.json"
        self.items = self._load()

    def _load(self) -> list[dict]:
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                return []
            return [
                item for item in payload.get("pets", [])
                if isinstance(item, dict)
                and CUSTOM_ID_PATTERN.fullmatch(str(item.get("id", "")))
            ][:24]
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return []

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"schema_version": 1, "pets": self.items},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.index_path)

    @staticmethod
    def _validate_name(name: str) -> str:
        value = " ".join(str(name).split())
        if not value:
            raise ValueError("先给这位新成员写一个名字")
        if len(value) > 12:
            raise ValueError("宠物名字最多12个字")
        if any(character in value for character in "<>\\/{}"):
            raise ValueError("宠物名字包含不支持的字符")
        return value

    @staticmethod
    def _decode_data_url(image_data: str) -> tuple[bytes, str]:
        match = re.fullmatch(
            r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\r\n]+)",
            str(image_data or ""),
            re.IGNORECASE,
        )
        if not match:
            raise ValueError("请选择 PNG、JPG 或 WebP 宠物照片")
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("照片内容无法读取") from None
        if not raw or len(raw) > MAX_UPLOAD_BYTES:
            raise ValueError("照片需小于6MB")
        extension = "jpg" if match.group(1).casefold() in {"jpg", "jpeg"} else match.group(1).casefold()
        return raw, extension

    @staticmethod
    def _open_photo(raw: bytes) -> Image.Image:
        try:
            with Image.open(io.BytesIO(raw)) as source:
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
        except (OSError, ValueError, Image.DecompressionBombError):
            raise ValueError("这张照片无法安全解析，请换一张清晰宠物照") from None
        if max(image.size) > MAX_IMAGE_SIDE or min(image.size) < 96:
            raise ValueError("照片尺寸需在96到6000像素之间")
        return image

    @staticmethod
    def _cartoon_base(photo: Image.Image) -> Image.Image:
        size = 720
        fitted = ImageOps.fit(
            photo,
            (size, size),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.43),
        )
        smooth = fitted.filter(ImageFilter.MedianFilter(5))
        color = ImageEnhance.Color(smooth).enhance(1.22)
        color = ImageEnhance.Contrast(color).enhance(1.08)
        posterized = ImageOps.posterize(color, 5)
        edges = fitted.convert("L").filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.autocontrast(edges).point(lambda value: 255 if value < 42 else 82)
        edge_rgb = Image.merge("RGB", (edges, edges, edges))
        return ImageChops.multiply(posterized, edge_rgb)

    @staticmethod
    def _stage_image(base: Image.Image, stage: int) -> Image.Image:
        canvas_size = (560, 340)
        palettes = (
            ("#EAF8E8", "#A7D5A4", "#F6B7B2"),
            ("#E5F5E2", "#78B97B", "#F0A99F"),
            ("#DDF0D9", "#4D925B", "#E99380"),
            ("#D1E8CE", "#2F6B43", "#E4B45D"),
        )
        background, border, accent = palettes[stage]
        canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.ellipse((76, 284, 484, 326), fill=(40, 80, 55, 35))

        sizes = (224, 256, 286, 304)
        diameter = sizes[stage]
        x = (canvas_size[0] - diameter) // 2
        y = 38 - stage * 3
        portrait = base.resize((diameter, diameter), Image.Resampling.LANCZOS)
        mask = Image.new("L", (diameter, diameter), 0)
        ImageDraw.Draw(mask).ellipse((4, 4, diameter - 4, diameter - 4), fill=255)
        portrait.putalpha(mask)

        frame = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        frame_draw = ImageDraw.Draw(frame)
        frame_draw.ellipse(
            (x - 9, y - 9, x + diameter + 9, y + diameter + 9),
            fill=background,
            outline=border,
            width=9,
        )
        frame.alpha_composite(portrait, (x, y))
        canvas.alpha_composite(frame)

        # A visible growth marker: collar becomes richer as focus time grows.
        collar_y = min(286, y + diameter - 24)
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle(
            (x + diameter * 0.23, collar_y, x + diameter * 0.77, collar_y + 16),
            radius=8,
            fill=accent,
            outline=border,
            width=2,
        )
        draw.ellipse(
            (
                canvas_size[0] / 2 - 9,
                collar_y + 8,
                canvas_size[0] / 2 + 9,
                collar_y + 26,
            ),
            fill="#FFF4CE" if stage < 3 else "#FFD768",
            outline=border,
            width=2,
        )
        if stage == 0:
            draw.ellipse((x + 30, y + 28, x + 44, y + 42), fill="#FFFFFF99")
        if stage == 3:
            draw.arc((x - 22, y - 22, x + 44, y + 44), 190, 350, fill="#E4B45D", width=5)
            draw.arc(
                (x + diameter - 44, y - 22, x + diameter + 22, y + 44),
                190,
                350,
                fill="#E4B45D",
                width=5,
            )
        return canvas

    @staticmethod
    def _remove_uniform_background(image: Image.Image) -> Image.Image:
        """Make the solid contact-sheet background transparent."""
        rgba = image.convert("RGBA")
        width, height = rgba.size
        samples = (
            rgba.getpixel((2, 2)),
            rgba.getpixel((max(0, width - 3), 2)),
            rgba.getpixel((2, max(0, height - 3))),
            rgba.getpixel((max(0, width - 3), max(0, height - 3))),
        )
        background = tuple(sum(pixel[channel] for pixel in samples) // 4 for channel in range(3))
        solid = Image.new("RGB", rgba.size, background)
        difference = ImageChops.difference(rgba.convert("RGB"), solid).convert("L")
        alpha = difference.point(lambda value: max(0, min(255, (value - 18) * 8)))
        alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
        rgba.putalpha(alpha)
        return rgba

    @staticmethod
    def _split_action_sheet(sheet: Image.Image) -> dict[str, Image.Image]:
        """Split the AI-generated 2x2 sheet in reading order."""
        width, height = sheet.size
        half_width, half_height = width // 2, height // 2
        inset_x = max(2, width // 100)
        inset_y = max(2, height // 100)
        boxes = (
            (inset_x, inset_y, half_width - inset_x, half_height - inset_y),
            (half_width + inset_x, inset_y, width - inset_x, half_height - inset_y),
            (inset_x, half_height + inset_y, half_width - inset_x, height - inset_y),
            (half_width + inset_x, half_height + inset_y, width - inset_x, height - inset_y),
        )
        return {
            action: CustomPetStore._remove_uniform_background(sheet.crop(box))
            for action, box in zip(ACTION_FILES, boxes, strict=True)
        }

    @staticmethod
    def _action_image(base: Image.Image, action: str) -> Image.Image:
        """Place one expression/action on a transparent native-alert canvas."""
        canvas = Image.new("RGBA", (560, 340), (0, 0, 0, 0))
        subject = base.convert("RGBA")
        if subject.getextrema()[3] == (255, 255):
            diameter = min(subject.size)
            mask = Image.new("L", subject.size, 0)
            ImageDraw.Draw(mask).ellipse(
                (
                    (subject.width - diameter) // 2,
                    (subject.height - diameter) // 2,
                    (subject.width + diameter) // 2,
                    (subject.height + diameter) // 2,
                ),
                fill=255,
            )
            subject.putalpha(mask)
        subject.thumbnail((390, 318), Image.Resampling.LANCZOS)
        if action == "wiggle":
            subject = subject.rotate(5, resample=Image.Resampling.BICUBIC, expand=True)
        x = (canvas.width - subject.width) // 2
        y = max(5, canvas.height - subject.height - 12)
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).ellipse((112, 296, 448, 330), fill=(25, 69, 47, 45))
        canvas.alpha_composite(shadow)
        canvas.alpha_composite(subject, (x, y))

        draw = ImageDraw.Draw(canvas)
        if action == "happy":
            draw.ellipse((157, 204, 199, 225), fill=(246, 139, 148, 105))
            draw.ellipse((361, 204, 403, 225), fill=(246, 139, 148, 105))
            draw.arc((246, 212, 314, 256), 12, 168, fill="#F4A2A8", width=5)
        elif action == "wiggle":
            draw.arc((84, 112, 146, 174), 120, 248, fill="#75AE83", width=5)
            draw.arc((414, 92, 480, 166), 292, 70, fill="#75AE83", width=5)
        elif action == "angry":
            draw.line((182, 150, 229, 169), fill="#5C3030", width=8)
            draw.line((331, 169, 378, 150), fill="#5C3030", width=8)
            draw.polygon(((438, 226), (481, 211), (468, 252)), fill="#E57B72")
        return canvas

    def create(
        self,
        name: str,
        image_data: str,
        *,
        renderer: str = "local-cartoon-v1",
    ) -> dict:
        if len(self.items) >= 12:
            raise ValueError("猫窝最多收养12位成员，请先送别一位再添加")
        pet_name = self._validate_name(name)
        raw, extension = self._decode_data_url(image_data)
        photo = self._open_photo(raw)
        custom_id = secrets.token_hex(8)
        pet_root = self.root / custom_id
        pet_root.mkdir(parents=True, exist_ok=False)
        try:
            (pet_root / f"original.{extension}").write_bytes(raw)
            is_ai_sheet = renderer.startswith("gemini")
            if is_ai_sheet:
                action_sources = self._split_action_sheet(photo)
            else:
                local_cartoon = self._cartoon_base(photo)
                action_sources = {
                    action: local_cartoon.copy()
                    for action in ACTION_FILES
                }
            idle = action_sources["idle"].convert("RGBA")
            cartoon = Image.new("RGB", idle.size, "#EAF8E8")
            cartoon.paste(idle.convert("RGB"), mask=idle.getchannel("A"))
            for stage, filename in enumerate(STAGE_FILES):
                self._stage_image(cartoon, stage).save(
                    pet_root / filename,
                    "PNG",
                    optimize=True,
                )
            for action, filename in ACTION_FILES.items():
                self._action_image(action_sources[action], action).save(
                    pet_root / filename,
                    "PNG",
                    optimize=True,
                )
            item = {
                "id": custom_id,
                "name": pet_name,
                "description": (
                    "由AI生成一致角色的四种动作，并在本机生成四段成长形态"
                    if renderer.startswith("gemini")
                    else "由你的照片在本机生成，会随专注时长一起长大"
                ),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "renderer": renderer,
            }
            self.items = [item, *self.items]
            self._save()
            return self.catalog_item(item)
        except Exception:
            shutil.rmtree(pet_root, ignore_errors=True)
            raise

    def delete(self, custom_id: str) -> bool:
        if not CUSTOM_ID_PATTERN.fullmatch(str(custom_id)):
            raise ValueError("自定义宠物编号不合法")
        existing = next((item for item in self.items if item["id"] == custom_id), None)
        if existing is None:
            raise ValueError("这位宠物已经不在猫窝里")
        pet_root = (self.root / custom_id).resolve()
        root = self.root.resolve()
        if root not in pet_root.parents:
            raise ValueError("宠物目录不合法")
        shutil.rmtree(pet_root, ignore_errors=False)
        self.items = [item for item in self.items if item["id"] != custom_id]
        self._save()
        return True

    @staticmethod
    def catalog_item(item: dict) -> dict:
        custom_id = item["id"]
        skin_id = f"{CUSTOM_PREFIX}{custom_id}"
        stage_urls = [
            f"/media/custom-pet/{custom_id}/{filename}" for filename in STAGE_FILES
        ]
        action_urls = {
            action: f"/media/custom-pet/{custom_id}/{filename}"
            for action, filename in ACTION_FILES.items()
        }
        return {
            **item,
            "custom_id": custom_id,
            "id": skin_id,
            "skin": skin_id,
            "custom": True,
            "asset_url": stage_urls[2],
            "young_asset_url": stage_urls[0],
            "stage_assets": stage_urls,
            "action_assets": action_urls,
        }

    def catalog(self) -> list[dict]:
        return [
            self.catalog_item(item)
            for item in self.items
            if custom_pet_exists(item["id"], self.root)
        ]

    def exists(self, custom_id: str) -> bool:
        return custom_pet_exists(custom_id, self.root)
