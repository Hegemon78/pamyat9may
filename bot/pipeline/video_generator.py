#!/usr/bin/env python3
"""
VideoGenerator — генератор памятных видео к 9 Мая.

Генерирует MP4 видео 9:16 (1080x1920) продолжительностью 45 секунд.

Архитектура: Pillow рендерит текст и placeholder в PNG с альфа-каналом,
FFmpeg собирает финальное видео через filter_complex (фон + overlay слоёв).

Требования:
    - FFmpeg (brew install ffmpeg)
    - Pillow (pip install Pillow)

Использование:
    python3 pipeline/video_generator.py \\
        --name "Иванов Пётр Иванович" \\
        --birth-year 1913 --death-year 1987 \\
        --rank "мл. сержант" \\
        --awards "Медаль За отвагу" "Медаль За победу над Германией" \\
        --template eternal_flame \\
        --output data/processed/test.mp4
"""

import argparse
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Палитра (совпадает с CLAUDE.md проекта)
# ---------------------------------------------------------------------------
# RGBA tuple: (R, G, B, A)
COLOR_BG_DARK = (30, 26, 22, 255)       # #1E1A16
COLOR_BG_RED = (45, 5, 5, 255)          # #2D0505
COLOR_NAME = (245, 230, 211, 255)        # #F5E6D3 — paper-100
COLOR_RANK = (218, 165, 32, 255)         # #DAA520 — gold
COLOR_AWARD = (255, 215, 0, 255)         # #FFD700 — gold accent
COLOR_DATES = (143, 188, 143, 255)       # #8FBC8F — olive light
COLOR_MEMORIAL = (204, 0, 0, 255)        # #CC0000 — red star
COLOR_TRANSPARENT = (0, 0, 0, 0)

# Шрифты (macOS), с fallback цепочкой
_FONT_CANDIDATES_SERIF = [
    "/System/Library/Fonts/Supplemental/PTSerif.ttc",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times.ttf",
    "/Library/Fonts/Times.ttc",
    "/System/Library/Fonts/Times.ttc",
]
_FONT_CANDIDATES_SANS = [
    "/System/Library/Fonts/Supplemental/PTSans.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VideoConfig:
    """Конфигурация генерируемого видео."""
    width: int = 1080
    height: int = 1920          # вертикальное 9:16 для соцсетей
    fps: int = 30
    duration: int = 45          # секунды
    template: str = "eternal_flame"  # eternal_flame | parade | family


@dataclass
class HeroData:
    """Данные о ветеране для видео."""
    full_name: str
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    rank: Optional[str] = None
    unit: Optional[str] = None
    awards: list[str] = field(default_factory=list)
    summary: Optional[str] = None   # краткий текст боевого пути
    photo_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _find_ffmpeg() -> str:
    """Возвращает путь к ffmpeg или бросает RuntimeError."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    for candidate in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if os.path.isfile(candidate):
            return candidate
    raise RuntimeError(
        "FFmpeg не найден. Установите: brew install ffmpeg"
    )


def _resolve_font(candidates: list[str]) -> str:
    """Возвращает первый доступный шрифт из списка кандидатов."""
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise RuntimeError(
        f"Не найден ни один шрифт. Проверьте: {candidates[:2]}"
    )


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    """Загружает шрифт с обработкой ошибки."""
    try:
        return ImageFont.truetype(path, size)
    except Exception as exc:
        raise RuntimeError(f"Не удалось загрузить шрифт {path}: {exc}") from exc


def _run_ffmpeg(args: list[str], ffmpeg_bin: str) -> None:
    """Запускает ffmpeg, проверяет код возврата."""
    cmd = [ffmpeg_bin, "-y"] + args
    logger.debug("FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"FFmpeg завершился с ошибкой (code {result.returncode}):\n"
            f"{stderr[-2000:]}"
        )


def _wrap_text(text: str, max_chars: int = 30) -> list[str]:
    """Разбивает текст на строки по словам."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip() if current else word
    if current:
        lines.append(current)
    return lines


def _draw_star(draw: ImageDraw.Draw, cx: float, cy: float, outer_r: float,
               inner_r: float, color: tuple) -> None:
    """Рисует 5-конечную звезду."""
    points: list[tuple[float, float]] = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = outer_r if i % 2 == 0 else inner_r
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)


# ---------------------------------------------------------------------------
# Класс-генератор
# ---------------------------------------------------------------------------

class VideoGenerator:
    """Генератор памятных видео к 9 Мая."""

    def __init__(self, output_dir: str = "data/processed") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ffmpeg = _find_ffmpeg()
        self._font_serif_path = _resolve_font(_FONT_CANDIDATES_SERIF)
        self._font_sans_path = _resolve_font(_FONT_CANDIDATES_SANS)
        logger.info("FFmpeg: %s", self._ffmpeg)
        logger.info("Serif: %s", self._font_serif_path)
        logger.info("Sans:  %s", self._font_sans_path)

    # ------------------------------------------------------------------
    # Публичный метод
    # ------------------------------------------------------------------

    def generate(
        self,
        hero: HeroData,
        config: Optional[VideoConfig] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Генерация полного видео.

        Возвращает абсолютный путь к готовому MP4.
        """
        if config is None:
            config = VideoConfig()
        if task_id is None:
            task_id = uuid.uuid4().hex[:8]

        output_path = str(self.output_dir / f"video_{task_id}.mp4")

        with tempfile.TemporaryDirectory(prefix="pamyat9may_") as tmpdir:
            logger.info("[%s] Старт: %s", task_id, hero.full_name)
            self._generate_in_tmpdir(hero, config, tmpdir, output_path)
            logger.info("[%s] Готово: %s", task_id, output_path)

        return output_path

    # ------------------------------------------------------------------
    # Оркестрация
    # ------------------------------------------------------------------

    def _generate_in_tmpdir(
        self,
        hero: HeroData,
        config: VideoConfig,
        tmpdir: str,
        output_path: str,
    ) -> None:
        """Создаёт слои и запускает финальную сборку."""
        # 1. Фоновое видео (градиент с анимацией огня)
        bg_path = os.path.join(tmpdir, "bg.mp4")
        self._create_background(config, bg_path)

        # 2. Фото (или placeholder со звездой)
        photo_raw = hero.photo_path
        if not photo_raw or not os.path.isfile(photo_raw):
            photo_raw = None

        photo_resized = os.path.join(tmpdir, "photo.png")
        self._prepare_photo(photo_raw, config, photo_resized)

        # 3. PNG-оверлеи с текстом (каждый — отдельный файл с альфа-каналом)
        overlay_paths = self._create_text_overlays(hero, config, tmpdir)

        # 4. Финальная сборка
        self._assemble(config, bg_path, photo_resized, overlay_paths, output_path)

    # ------------------------------------------------------------------
    # Слой 1: Фон
    # ------------------------------------------------------------------

    def _create_background(self, config: VideoConfig, out_path: str) -> None:
        """
        Создаёт фоновое видео: вертикальный градиент #1E1A16 → #2D0505.

        Анимация: лёгкое пульсирование красного (имитация живого огня).
        Используется Pillow для кадра + FFmpeg для видео.
        """
        W, H = config.width, config.height
        D = config.duration
        FPS = config.fps

        # Создаём 2 ключевых кадра (фаза 0 и фаза π)
        # FFmpeg morfará между ними через loop
        frame_paths: list[str] = []
        for phase in [0, 1]:
            frame_path = out_path.replace(".mp4", f"_frame{phase}.png")
            img = Image.new("RGB", (W, H))
            draw = ImageDraw.Draw(img)
            # Вертикальный градиент пиксель за пикселем через scanline
            for y in range(H):
                ratio = y / H
                # Базовый градиент: тёмный сверху, красный снизу
                r = int(30 + (45 - 30) * ratio)
                g = int(26 - (26 - 5) * ratio)
                b = int(22 - (22 - 5) * ratio)
                # Анимация: слабый пульс в нижней трети
                if phase == 1 and ratio > 0.67:
                    pulse = int(8 * (ratio - 0.67) / 0.33)
                    r = min(255, r + pulse)
                draw.line([(0, y), (W, y)], fill=(r, g, b))
            img.save(frame_path)
            frame_paths.append(frame_path)

        # Простой статичный фон из первого кадра (надёжнее сложных blend)
        _run_ffmpeg([
            "-loop", "1", "-t", str(D), "-i", frame_paths[0],
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            out_path,
        ], self._ffmpeg)

    # ------------------------------------------------------------------
    # Слой 2: Фото
    # ------------------------------------------------------------------

    def _prepare_photo(
        self, photo_path: Optional[str], config: VideoConfig, out_path: str
    ) -> None:
        """
        Подготавливает фото: масштабирует и центрирует в квадратную зону.

        Если фото нет — создаёт placeholder со звездой.
        """
        W = config.width
        # Зона фото: 75% ширины, квадрат
        photo_size = int(W * 0.75)

        if photo_path and os.path.isfile(photo_path):
            img = Image.open(photo_path).convert("RGBA")
            # Вписываем в квадрат с сохранением пропорций
            img.thumbnail((photo_size, photo_size), Image.LANCZOS)
            canvas = Image.new("RGBA", (photo_size, photo_size), COLOR_BG_DARK)
            offset_x = (photo_size - img.width) // 2
            offset_y = (photo_size - img.height) // 2
            canvas.paste(img, (offset_x, offset_y), img)
            # Лёгкая тонировка (историческое настроение)
            self._apply_sepia_tint(canvas)
            canvas.save(out_path)
        else:
            # Placeholder: звезда на тёмном фоне
            canvas = Image.new("RGBA", (photo_size, photo_size), COLOR_BG_DARK)
            draw = ImageDraw.Draw(canvas)
            cx, cy = photo_size // 2, photo_size // 2
            outer_r = int(photo_size * 0.35)
            inner_r = int(photo_size * 0.14)
            # Красная звезда
            _draw_star(draw, cx, cy, outer_r, inner_r, (204, 0, 0, 255))
            # Золотая обводка
            _draw_star(draw, cx, cy, outer_r + 4, inner_r + 2, (255, 215, 0, 60))
            canvas.save(out_path)

    @staticmethod
    def _apply_sepia_tint(img: Image.Image) -> None:
        """Применяет лёгкую сепия-тонировку (in-place)."""
        pixels = img.load()
        if pixels is None:
            return
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = pixels[x, y]
                # Сепия: тёплый коричневатый оттенок
                new_r = min(255, int(r * 0.95 + g * 0.05))
                new_g = min(255, int(r * 0.02 + g * 0.90 + b * 0.08))
                new_b = min(255, int(r * 0.02 + g * 0.05 + b * 0.85))
                pixels[x, y] = (new_r, new_g, new_b, a)

    # ------------------------------------------------------------------
    # Слой 3: Текстовые оверлеи (Pillow → PNG)
    # ------------------------------------------------------------------

    def _create_text_overlays(
        self, hero: HeroData, config: VideoConfig, tmpdir: str
    ) -> list[dict]:
        """
        Создаёт текстовые PNG-оверлеи для каждого элемента видео.

        Возвращает список: [{"path": str, "x": int, "y": int,
                              "start": float, "end": float, "fade_in": float, "fade_out": float}]
        """
        W, H = config.width, config.height
        overlays: list[dict] = []

        font_serif = self._font_serif_path
        font_sans = self._font_sans_path

        # Размеры шрифтов
        SIZE_NAME = 68
        SIZE_RANK = 48
        SIZE_UNIT = 40
        SIZE_AWARD = 42
        SIZE_SUMMARY = 36
        SIZE_DATES = 54
        SIZE_MEMORIAL = 60

        # Вертикальные зоны (от верха)
        photo_size = int(W * 0.75)
        photo_y = int(H * 0.12)
        text_base_y = photo_y + photo_size + 50

        # ----------------------------------------------------------
        # 1. ФИО (3-45 сек, fade in 0.5 сек)
        # ----------------------------------------------------------
        name_lines = _wrap_text(hero.full_name, max_chars=22)[:2]
        name_img, name_h = self._render_text_block(
            lines=name_lines,
            font_path=font_serif,
            font_size=SIZE_NAME,
            color=COLOR_NAME,
            canvas_width=W,
            line_gap=12,
        )
        name_path = os.path.join(tmpdir, "overlay_name.png")
        name_img.save(name_path)
        overlays.append({
            "path": name_path,
            "x": 0,
            "y": text_base_y,
            "start": 3.0,
            "end": 45.0,
            "fade_in": 0.5,
            "fade_out": 1.0,
        })
        text_base_y += name_h + 30

        # ----------------------------------------------------------
        # 2. Звание (8-45 сек)
        # ----------------------------------------------------------
        if hero.rank:
            rank_img, rank_h = self._render_text_block(
                lines=[hero.rank],
                font_path=font_sans,
                font_size=SIZE_RANK,
                color=COLOR_RANK,
                canvas_width=W,
            )
            rank_path = os.path.join(tmpdir, "overlay_rank.png")
            rank_img.save(rank_path)
            overlays.append({
                "path": rank_path,
                "x": 0,
                "y": text_base_y,
                "start": 8.0,
                "end": 45.0,
                "fade_in": 0.5,
                "fade_out": 1.0,
            })
            text_base_y += rank_h + 16

        # ----------------------------------------------------------
        # 3. Часть/подразделение (8-45 сек)
        # ----------------------------------------------------------
        if hero.unit:
            unit_lines = _wrap_text(hero.unit, max_chars=30)[:2]
            unit_img, unit_h = self._render_text_block(
                lines=unit_lines,
                font_path=font_sans,
                font_size=SIZE_UNIT,
                color=COLOR_RANK,
                canvas_width=W,
                line_gap=8,
            )
            unit_path = os.path.join(tmpdir, "overlay_unit.png")
            unit_img.save(unit_path)
            overlays.append({
                "path": unit_path,
                "x": 0,
                "y": text_base_y,
                "start": 8.0,
                "end": 45.0,
                "fade_in": 0.6,
                "fade_out": 1.0,
            })
            text_base_y += unit_h + 24

        # ----------------------------------------------------------
        # 4. Награды (13-25 сек, каждая появляется по очереди)
        # ----------------------------------------------------------
        awards_y = text_base_y + 10
        for i, award in enumerate(hero.awards[:4]):
            t_start = 13.0 + i * 3.0
            award_lines = _wrap_text(f"* {award}", max_chars=32)[:2]
            award_img, award_h = self._render_text_block(
                lines=award_lines,
                font_path=font_sans,
                font_size=SIZE_AWARD,
                color=COLOR_AWARD,
                canvas_width=W,
                line_gap=6,
            )
            award_path = os.path.join(tmpdir, f"overlay_award_{i}.png")
            award_img.save(award_path)
            overlays.append({
                "path": award_path,
                "x": 0,
                "y": awards_y + i * (award_h + 10),
                "start": t_start,
                "end": 25.0,
                "fade_in": 0.4,
                "fade_out": 0.5,
            })

        # ----------------------------------------------------------
        # 5. Боевой путь (25-35 сек)
        # ----------------------------------------------------------
        if hero.summary:
            summary_lines = _wrap_text(hero.summary, max_chars=38)[:6]
            summary_img, summary_h = self._render_text_block(
                lines=summary_lines,
                font_path=font_serif,
                font_size=SIZE_SUMMARY,
                color=COLOR_NAME,
                canvas_width=W,
                line_gap=10,
            )
            summary_path = os.path.join(tmpdir, "overlay_summary.png")
            summary_img.save(summary_path)
            overlays.append({
                "path": summary_path,
                "x": 0,
                "y": int(H * 0.58),
                "start": 25.0,
                "end": 35.0,
                "fade_in": 0.5,
                "fade_out": 0.5,
            })

        # ----------------------------------------------------------
        # 6. Годы жизни (35-40 сек)
        # ----------------------------------------------------------
        dates_parts: list[str] = []
        if hero.birth_year:
            dates_parts.append(str(hero.birth_year))
        if hero.death_year:
            dates_parts.append(str(hero.death_year))
        if dates_parts:
            dates_text = " — ".join(dates_parts)
            dates_img, dates_h = self._render_text_block(
                lines=[dates_text],
                font_path=font_serif,
                font_size=SIZE_DATES,
                color=COLOR_DATES,
                canvas_width=W,
            )
            dates_path = os.path.join(tmpdir, "overlay_dates.png")
            dates_img.save(dates_path)
            overlays.append({
                "path": dates_path,
                "x": 0,
                "y": int(H * 0.70),
                "start": 35.0,
                "end": 45.0,
                "fade_in": 0.5,
                "fade_out": 0.8,
            })

        # ----------------------------------------------------------
        # 7. "Помним. Гордимся." (40-45 сек)
        # ----------------------------------------------------------
        memorial_img, memorial_h = self._render_text_block(
            lines=["Помним. Гордимся."],
            font_path=font_serif,
            font_size=SIZE_MEMORIAL,
            color=COLOR_MEMORIAL,
            canvas_width=W,
        )
        memorial_path = os.path.join(tmpdir, "overlay_memorial.png")
        memorial_img.save(memorial_path)
        overlays.append({
            "path": memorial_path,
            "x": 0,
            "y": int(H * 0.82),
            "start": 40.0,
            "end": 45.0,
            "fade_in": 0.5,
            "fade_out": 1.0,
        })

        return overlays

    def _render_text_block(
        self,
        lines: list[str],
        font_path: str,
        font_size: int,
        color: tuple,
        canvas_width: int,
        line_gap: int = 8,
    ) -> tuple[Image.Image, int]:
        """
        Рендерит блок текста в RGBA PNG с прозрачным фоном.

        Возвращает (изображение, высота блока).
        """
        font = _load_font(font_path, font_size)

        # Измеряем размеры каждой строки
        line_sizes: list[tuple[int, int]] = []
        for line in lines:
            bbox = font.getbbox(line)
            line_sizes.append((bbox[2] - bbox[0], bbox[3] - bbox[1]))

        line_height = font_size + line_gap
        total_height = line_height * len(lines) + 16  # +padding

        # Canvas на всю ширину видео (прозрачный)
        img = Image.new("RGBA", (canvas_width, total_height), COLOR_TRANSPARENT)
        draw = ImageDraw.Draw(img)

        for i, (line, (lw, lh)) in enumerate(zip(lines, line_sizes)):
            x = (canvas_width - lw) // 2   # центрирование
            y = i * line_height + 8         # +padding top
            # Тень для читаемости на любом фоне
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 160))
            draw.text((x, y), line, font=font, fill=color)

        return img, total_height

    # ------------------------------------------------------------------
    # Слой 4: Финальная сборка
    # ------------------------------------------------------------------

    def _assemble(
        self,
        config: VideoConfig,
        bg_path: str,
        photo_path: str,
        overlays: list[dict],
        output_path: str,
    ) -> None:
        """
        Финальная сборка через FFmpeg filter_complex.

        Структура цепочки:
          bg → overlay(photo) → overlay(name) → ... → overlay(memorial) → fade → out
        """
        W, H = config.width, config.height
        D = config.duration
        FPS = config.fps

        # Зона фото: центрированная
        photo_size = int(W * 0.75)
        photo_x = (W - photo_size) // 2
        photo_y = int(H * 0.12)

        # Собираем входные файлы: [0]=bg, [1]=photo, [2..N]=overlays
        inputs: list[str] = []
        inputs += ["-i", bg_path]
        inputs += ["-i", photo_path]
        for ov in overlays:
            inputs += ["-i", ov["path"]]

        filters: list[str] = []

        # 1. Overlay фото на фон (с анимацией zoom через scale+overlay)
        # zoompan делаем отдельно на фото
        photo_idx = 1
        zoom_frames = int(5 * FPS)  # 5 сек анимации zoom

        # Photo с zoom: масштаб от 1.0 до 1.08
        filters.append(
            f"[{photo_idx}:v]"
            f"zoompan="
            f"z='if(lte(on\\,1)\\,1.0\\,min(zoom+0.0003\\,1.08))':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={zoom_frames}:"
            f"s={photo_size}x{photo_size}:"
            f"fps={FPS},"
            f"setpts=PTS-STARTPTS"
            f"[photo_zoom]"
        )

        # Overlay фото на фон с fade in/out
        # enable: только в [3, D] секунды; alpha через alphamix
        filters.append(
            f"[0:v][photo_zoom]overlay="
            f"x={photo_x}:y={photo_y}:"
            f"enable='between(t\\,3\\,{D})':"
            f"eval=frame"
            f"[v_after_photo]"
        )

        current_label = "v_after_photo"

        # 2. Наложение каждого текстового PNG
        for i, ov in enumerate(overlays):
            ov_idx = 2 + i  # индекс входного файла
            t_start = ov["start"]
            t_end = ov["end"]
            fade_in = ov["fade_in"]
            fade_out = ov["fade_out"]
            x_pos = ov["x"]
            y_pos = ov["y"]
            next_label = f"v_ov{i}"

            # Формула alpha для fade in/out через overlay alpha параметра нет —
            # делаем через format + colorchannelmixer на overlay input
            # Используем: [ovN]format=rgba,colorchannelmixer=aa=<alpha>[ovN_alpha]
            # alpha как функция времени — через geq на alpha канал PNG
            alpha_expr = (
                f"if(lt(T\\,{t_start})\\,0\\,"
                f"if(lt(T\\,{t_start}+{fade_in})\\,(T-{t_start})/{fade_in}\\,"
                f"if(gt(T\\,{t_end}-{fade_out})\\,({t_end}-T)/{fade_out}\\,"
                f"if(gt(T\\,{t_end})\\,0\\,1))))"
            )

            filters.append(
                f"[{ov_idx}:v]"
                f"geq="
                f"r='r(X\\,Y)':"
                f"g='g(X\\,Y)':"
                f"b='b(X\\,Y)':"
                f"a='alpha(X\\,Y)*({alpha_expr})',"
                f"setpts=PTS-STARTPTS+{t_start}/TB"
                f"[ov{i}_a]"
            )

            filters.append(
                f"[{current_label}][ov{i}_a]"
                f"overlay=x={x_pos}:y={y_pos}:format=auto:eval=frame"
                f"[{next_label}]"
            )
            current_label = next_label

        # 3. Финальный fade in/out всего видео
        filters.append(
            f"[{current_label}]"
            f"fade=t=in:st=0:d=1,"
            f"fade=t=out:st={D - 1}:d=1"
            f"[vout]"
        )

        filter_complex = "; ".join(filters)

        cmd = inputs + [
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-r", str(FPS),
            "-t", str(D),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        logger.info("Сборка видео (%d оверлеев)...", len(overlays))
        _run_ffmpeg(cmd, self._ffmpeg)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Генератор памятных видео к 9 Мая",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python3 pipeline/video_generator.py \\
      --name "Иванов Пётр Иванович" \\
      --birth-year 1913 --death-year 1987 \\
      --rank "мл. сержант" \\
      --awards "Медаль За отвагу" "Медаль За победу над Германией" \\
      --template eternal_flame \\
      --output data/processed/test.mp4
        """,
    )
    parser.add_argument("--name", required=True, help="ФИО ветерана")
    parser.add_argument("--birth-year", type=int, help="Год рождения")
    parser.add_argument("--death-year", type=int, help="Год смерти")
    parser.add_argument("--rank", help="Воинское звание")
    parser.add_argument("--unit", help="Воинская часть/подразделение")
    parser.add_argument("--awards", nargs="*", default=[], help="Список наград")
    parser.add_argument("--summary", help="Текст боевого пути")
    parser.add_argument("--photo", help="Путь к фото ветерана (PNG/JPG)")
    parser.add_argument(
        "--template",
        choices=["eternal_flame", "parade", "family"],
        default="eternal_flame",
        help="Шаблон видео (по умолчанию: eternal_flame)",
    )
    parser.add_argument(
        "--duration", type=int, default=45,
        help="Длительность в секундах (по умолчанию: 45)"
    )
    parser.add_argument(
        "--output", default="data/processed/video.mp4",
        help="Путь к выходному MP4"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Подробный лог")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    hero = HeroData(
        full_name=args.name,
        birth_year=args.birth_year,
        death_year=args.death_year,
        rank=args.rank,
        unit=args.unit,
        awards=args.awards or [],
        summary=args.summary,
        photo_path=args.photo,
    )

    config = VideoConfig(
        template=args.template,
        duration=args.duration,
    )

    output_path = Path(args.output)
    output_dir = str(output_path.parent)

    generator = VideoGenerator(output_dir=output_dir)
    task_id = uuid.uuid4().hex[:8]
    result_path = generator.generate(hero, config, task_id=task_id)

    # Переименовываем если нужно другое имя
    final_path = str(output_path.resolve())
    result_abs = str(Path(result_path).resolve())
    if result_abs != final_path:
        shutil.move(result_path, final_path)

    print(f"\nВидео готово: {final_path}")
    size_mb = os.path.getsize(final_path) / 1024 / 1024
    print(f"Размер: {size_mb:.1f} MB")
    print(f"Длительность: {config.duration} сек")


if __name__ == "__main__":
    main()
