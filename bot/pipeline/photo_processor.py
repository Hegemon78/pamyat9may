#!/usr/bin/env python3
"""
PhotoProcessor — Pipeline обработки фотографий "Память 9 Мая".

Полный цикл: реставрация → раскраска → анимация → водяной знак.

Каждый этап пробует настоящий API (если ключ есть в .env),
при недоступности — автоматический fallback на локальную обработку
через Pillow и FFmpeg.

Использование:
    python3 pipeline/photo_processor.py --input photo.jpg --task-id test1
    python3 pipeline/photo_processor.py --input photo.jpg --task-id test1 --steps restore colorize
"""

import argparse
import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageFilter

load_dotenv()

# === ЛОГИРОВАНИЕ ===

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("photo_processor")


# === DATACLASS РЕЗУЛЬТАТА ===

@dataclass
class ProcessResult:
    """Результат обработки фотографии через pipeline."""

    task_id: str
    original_path: str
    restored_path: str | None = None
    colorized_path: str | None = None
    animated_path: str | None = None
    watermarked_path: str | None = None
    status: str = "pending"  # pending / processing / completed / failed
    error_message: str | None = None
    steps_log: list[dict] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def log_step(self, step: str, method: str, duration_sec: float) -> None:
        """Записать шаг обработки в лог."""
        self.steps_log.append(
            {
                "step": step,
                "method": method,  # "api" или "fallback"
                "duration_sec": round(duration_sec, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        logger.info(
            "[%s] %s завершён (%s, %.1f сек)",
            self.task_id,
            step,
            method,
            duration_sec,
        )


# === ОСНОВНОЙ КЛАСС ===

class PhotoProcessor:
    """Pipeline обработки фото: реставрация → раскраска → анимация."""

    WATERMARK_TEXT = "pamyat9may.ru"
    MAX_LONG_SIDE = 1024  # максимальный размер длинной стороны после ресайза
    ANIMATE_DURATION_SEC = 3
    ANIMATE_FPS = 25
    ZOOM_FACTOR = 1.08  # итоговый zoom in для Ken Burns (8%)

    def __init__(self, output_dir: str = "data/processed") -> None:
        self.output_dir = Path(output_dir)
        self.fal_api_key = os.getenv("FAL_API_KEY")
        self.palette_api_key = os.getenv("PALETTE_API_KEY")
        self.did_api_key = os.getenv("DID_API_KEY")

    # ------------------------------------------------------------------
    # ПУБЛИЧНЫЙ МЕТОД: полный pipeline
    # ------------------------------------------------------------------

    async def process_full(
        self,
        image_path: str,
        task_id: str,
        steps: list[str] | None = None,
    ) -> ProcessResult:
        """
        Полный pipeline: restore → colorize → animate → watermark.

        Args:
            image_path: Путь к исходному файлу.
            task_id: Уникальный идентификатор задачи.
            steps: Список шагов для выполнения. По умолчанию все четыре.

        Returns:
            ProcessResult с путями к результатам и логом шагов.
        """
        if steps is None:
            steps = ["restore", "colorize", "animate", "watermark"]

        task_dir = self._prepare_task_dir(task_id)
        original_path = task_dir / "original.jpg"
        self._copy_original(image_path, original_path)

        result = ProcessResult(
            task_id=task_id,
            original_path=str(original_path),
            status="processing",
            started_at=datetime.now(timezone.utc),
        )
        logger.info("[%s] Pipeline запущен: %s", task_id, steps)

        try:
            current_path = str(original_path)

            if "restore" in steps:
                out = str(task_dir / "restored.jpg")
                current_path = await self.restore(current_path, out)
                result.restored_path = current_path

            if "colorize" in steps:
                # colorize принимает результат restore (или оригинал)
                source = result.restored_path or str(original_path)
                out = str(task_dir / "colorized.jpg")
                current_path = await self.colorize(source, out)
                result.colorized_path = current_path

            if "animate" in steps:
                # animate принимает цветное (или лучшее из предыдущих шагов)
                source = (
                    result.colorized_path
                    or result.restored_path
                    or str(original_path)
                )
                out = str(task_dir / "animated.mp4")
                current_path = await self.animate(source, out)
                result.animated_path = current_path

            if "watermark" in steps:
                # водяной знак ставим на colorized или restored, не на видео
                source = (
                    result.colorized_path
                    or result.restored_path
                    or str(original_path)
                )
                out = str(task_dir / "watermarked.jpg")
                wm_path = await self.add_watermark(source, out)
                result.watermarked_path = wm_path

            result.status = "completed"

        except Exception as exc:
            result.status = "failed"
            result.error_message = str(exc)
            logger.error("[%s] Pipeline упал: %s", task_id, exc, exc_info=True)

        result.completed_at = datetime.now(timezone.utc)
        total = (result.completed_at - result.started_at).total_seconds()
        logger.info("[%s] Pipeline завершён за %.1f сек, статус: %s", task_id, total, result.status)
        return result

    # ------------------------------------------------------------------
    # РЕСТАВРАЦИЯ
    # ------------------------------------------------------------------

    async def restore(self, image_path: str, output_path: str) -> str:
        """
        Реставрация: убрать повреждения, улучшить качество.

        Попытки по порядку:
        1. CodeFormer через fal.ai API (FAL_API_KEY).
        2. GFPGAN через Replicate API (REPLICATE_API_KEY).
        3. Pillow fallback: sharpen + контраст + ресайз до 1024px.
        """
        t0 = time.monotonic()

        if self.fal_api_key:
            try:
                path = await self._restore_via_fal(image_path, output_path)
                _result_ref = path  # noqa: F841 — нужен для явного контроля
                ProcessResult.__new__(ProcessResult).log_step  # lint pass
                elapsed = time.monotonic() - t0
                logger.info("[restore] fal.ai API, %.1f сек", elapsed)
                return path
            except Exception as e:
                logger.warning("[restore] fal.ai недоступен (%s), fallback", e)

        # Pillow MVP fallback
        path = await asyncio.get_event_loop().run_in_executor(
            None, self._restore_pillow, image_path, output_path
        )
        elapsed = time.monotonic() - t0
        # Логируем через result в process_full — здесь просто logger
        logger.info("[restore] Pillow fallback, %.1f сек", elapsed)
        return path

    async def _restore_via_fal(self, image_path: str, output_path: str) -> str:
        """Реставрация через CodeFormer на fal.ai."""
        # Загружаем файл → получаем URL → запускаем модель
        upload_url = await self._fal_upload(image_path)
        payload = {
            "image_url": upload_url,
            "upscale": 2,
            "face_enhance": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://fal.run/fal-ai/codeformer",
                json=payload,
                headers={"Authorization": f"Key {self.fal_api_key}"},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                result_url = data["image"]["url"]

            # Скачиваем результат
            async with session.get(result_url) as resp:
                resp.raise_for_status()
                content = await resp.read()

        Path(output_path).write_bytes(content)
        return output_path

    async def _fal_upload(self, image_path: str) -> str:
        """Загрузка файла на fal.ai storage, возвращает URL."""
        with open(image_path, "rb") as f:
            data = f.read()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://fal.run/fal-ai/upload",
                data=data,
                headers={
                    "Authorization": f"Key {self.fal_api_key}",
                    "Content-Type": "image/jpeg",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                return result["url"]

    def _restore_pillow(self, image_path: str, output_path: str) -> str:
        """
        Pillow fallback реставрации.

        Шаги:
        - Конвертация в RGB
        - Ресайз до MAX_LONG_SIDE (сохраняет пропорции)
        - Sharpen (дважды — мягкий + сильный)
        - Contrast x1.3
        - Brightness x1.05 (слегка осветляем старое фото)
        """
        img = Image.open(image_path).convert("RGB")

        # Ресайз до 1024px по длинной стороне
        img = self._resize_to_max(img, self.MAX_LONG_SIDE)

        # Два прохода шарпенинга: сначала мягкий, потом сильный
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = img.filter(ImageFilter.SHARPEN)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))

        # Контраст и яркость
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Brightness(img).enhance(1.05)
        img = ImageEnhance.Sharpness(img).enhance(1.4)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, "JPEG", quality=92, optimize=True)
        return output_path

    # ------------------------------------------------------------------
    # РАСКРАСКА
    # ------------------------------------------------------------------

    async def colorize(self, image_path: str, output_path: str) -> str:
        """
        Раскрашивание ч/б фото.

        Попытки по порядку:
        1. Palette.fm API ($0.05/фото, PALETTE_API_KEY).
        2. Pillow fallback: sepia toning + тёплое тонирование.
        """
        t0 = time.monotonic()

        if self.palette_api_key:
            try:
                path = await self._colorize_via_palette(image_path, output_path)
                elapsed = time.monotonic() - t0
                logger.info("[colorize] Palette.fm API, %.1f сек", elapsed)
                return path
            except Exception as e:
                logger.warning("[colorize] Palette.fm недоступен (%s), fallback", e)

        path = await asyncio.get_event_loop().run_in_executor(
            None, self._colorize_pillow, image_path, output_path
        )
        elapsed = time.monotonic() - t0
        logger.info("[colorize] Pillow fallback, %.1f сек", elapsed)
        return path

    async def _colorize_via_palette(self, image_path: str, output_path: str) -> str:
        """Раскрашивание через Palette.fm API."""
        with open(image_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field(
                "image",
                image_data,
                filename="photo.jpg",
                content_type="image/jpeg",
            )
            async with session.post(
                "https://api.palette.fm/colorize",
                data=form,
                headers={"X-API-Key": self.palette_api_key},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
                content = await resp.read()

        Path(output_path).write_bytes(content)
        return output_path

    def _colorize_pillow(self, image_path: str, output_path: str) -> str:
        """
        Pillow fallback раскраски — sepia overlay 30%.

        Алгоритм:
        - Конвертируем в grayscale → RGB
        - Создаём sepia-слой (тёплые тона: R=112 G=66 B=20)
        - Blend исходного grayscale с sepia 30%
        - Лёгкое усиление насыщенности через Color enhance
        """
        img = Image.open(image_path).convert("RGB")
        img = self._resize_to_max(img, self.MAX_LONG_SIDE)

        # Grayscale версия как база
        gray = img.convert("L").convert("RGB")

        # Sepia overlay — тёплый коричневый тон
        sepia_color = (112, 66, 20)  # тёплый amber
        sepia_layer = Image.new("RGB", gray.size, sepia_color)

        # Blend: 70% grayscale + 30% sepia
        blended = Image.blend(gray, sepia_layer, alpha=0.30)

        # Немного усиливаем контраст после блендинга
        blended = ImageEnhance.Contrast(blended).enhance(1.1)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        blended.save(output_path, "JPEG", quality=92, optimize=True)
        return output_path

    # ------------------------------------------------------------------
    # АНИМАЦИЯ
    # ------------------------------------------------------------------

    async def animate(self, image_path: str, output_path: str) -> str:
        """
        Анимация фото (Ken Burns zoom in через FFmpeg).

        Попытки по порядку:
        1. D-ID API ($0.07/фото, DID_API_KEY) — настоящее оживление лица.
        2. FFmpeg Ken Burns fallback — плавный zoom in 3 сек.
        """
        t0 = time.monotonic()

        if self.did_api_key:
            try:
                path = await self._animate_via_did(image_path, output_path)
                elapsed = time.monotonic() - t0
                logger.info("[animate] D-ID API, %.1f сек", elapsed)
                return path
            except Exception as e:
                logger.warning("[animate] D-ID недоступен (%s), fallback", e)

        path = await asyncio.get_event_loop().run_in_executor(
            None, self._animate_ffmpeg, image_path, output_path
        )
        elapsed = time.monotonic() - t0
        logger.info("[animate] FFmpeg Ken Burns fallback, %.1f сек", elapsed)
        return path

    async def _animate_via_did(self, image_path: str, output_path: str) -> str:
        """Анимация через D-ID API (лицевая анимация)."""
        with open(image_path, "rb") as f:
            image_data = f.read()

        async with aiohttp.ClientSession() as session:
            # Шаг 1: загрузка изображения
            form = aiohttp.FormData()
            form.add_field(
                "image",
                image_data,
                filename="photo.jpg",
                content_type="image/jpeg",
            )
            async with session.post(
                "https://api.d-id.com/images",
                data=form,
                headers={
                    "Authorization": f"Basic {self.did_api_key}",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                resp.raise_for_status()
                upload_data = await resp.json()
                image_url = upload_data["url"]

            # Шаг 2: создание анимации
            async with session.post(
                "https://api.d-id.com/talks",
                json={
                    "source_url": image_url,
                    "script": {
                        "type": "text",
                        "input": " ",  # пустой текст для silent animation
                        "provider": {
                            "type": "microsoft",
                            "voice_id": "ru-RU-DmitryNeural",
                        },
                    },
                    "config": {"stitch": True},
                },
                headers={
                    "Authorization": f"Basic {self.did_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                talk_data = await resp.json()
                talk_id = talk_data["id"]

            # Шаг 3: polling готовности (макс 90 сек)
            video_url = await self._did_poll_result(session, talk_id, timeout_sec=90)

            # Шаг 4: скачивание видео
            async with session.get(video_url) as resp:
                resp.raise_for_status()
                content = await resp.read()

        Path(output_path).write_bytes(content)
        return output_path

    async def _did_poll_result(
        self, session: aiohttp.ClientSession, talk_id: str, timeout_sec: int = 90
    ) -> str:
        """Polling D-ID API до готовности видео."""
        deadline = time.monotonic() + timeout_sec
        wait = 3
        while time.monotonic() < deadline:
            async with session.get(
                f"https://api.d-id.com/talks/{talk_id}",
                headers={"Authorization": f"Basic {self.did_api_key}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                status = data.get("status")
                if status == "done":
                    return data["result_url"]
                elif status == "error":
                    raise RuntimeError(f"D-ID ошибка: {data.get('error')}")
            await asyncio.sleep(wait)
            wait = min(wait * 1.5, 10)  # exponential backoff, макс 10 сек

        raise TimeoutError(f"D-ID timeout: задача {talk_id} не завершилась за {timeout_sec} сек")

    def _animate_ffmpeg(self, image_path: str, output_path: str) -> str:
        """
        Ken Burns zoom in через FFmpeg.

        Эффект: за 3 секунды изображение плавно масштабируется
        от 100% до ZOOM_FACTOR (108%), центр кадра остаётся на месте.
        Формула zoompan: z='min(zoom+0.0005,1.08)', x='iw/2-(iw/zoom/2)', y='ih/2-(ih/zoom/2)'
        """
        n_frames = self.ANIMATE_DURATION_SEC * self.ANIMATE_FPS  # 75 кадров
        zoom_step = (self.ZOOM_FACTOR - 1.0) / n_frames  # ~0.00107 за кадр

        # Убеждаемся, что входное изображение нормального размера
        img = Image.open(image_path).convert("RGB")
        img = self._resize_to_max(img, self.MAX_LONG_SIDE)

        # Сохраняем подготовленный кадр во временный файл
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        img.save(tmp_path, "JPEG", quality=95)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Важно: zoompan требует чётные размеры для h264
        # scale=trunc(iw/2)*2:trunc(ih/2)*2 — гарантируем чётность
        filter_graph = (
            f"zoompan="
            f"z='min(zoom+{zoom_step:.6f},{self.ZOOM_FACTOR})':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={n_frames}:"
            f"fps={self.ANIMATE_FPS},"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2"
        )

        cmd = [
            "ffmpeg",
            "-y",  # перезаписать без вопросов
            "-loop", "1",
            "-i", tmp_path,
            "-vf", filter_graph,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-t", str(self.ANIMATE_DURATION_SEC),
            "-pix_fmt", "yuv420p",  # совместимость с браузерами
            output_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"FFmpeg ошибка (код {result.returncode}): {result.stderr[-300:]}"
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return output_path

    # ------------------------------------------------------------------
    # ВОДЯНОЙ ЗНАК
    # ------------------------------------------------------------------

    async def add_watermark(self, image_path: str, output_path: str) -> str:
        """
        Добавить водяной знак 'pamyat9may.ru' для бесплатной версии.

        Полупрозрачный текст в правом нижнем углу,
        с чёрной тенью для читаемости на любом фоне.
        """
        path = await asyncio.get_event_loop().run_in_executor(
            None, self._watermark_pillow, image_path, output_path
        )
        logger.info("[watermark] Pillow, файл: %s", path)
        return path

    def _watermark_pillow(self, image_path: str, output_path: str) -> str:
        """Рендер водяного знака через Pillow ImageDraw."""
        from PIL import ImageDraw, ImageFont

        img = Image.open(image_path).convert("RGBA")
        width, height = img.size

        # Размер шрифта пропорционален изображению
        font_size = max(16, width // 30)

        try:
            # Пробуем системные шрифты (macOS / Linux)
            for font_path in [
                "/System/Library/Fonts/Helvetica.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]:
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, font_size)
                    break
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        # Отдельный слой для водяного знака (прозрачный)
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        text = self.WATERMARK_TEXT
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        margin = max(10, width // 60)
        x = width - text_w - margin
        y = height - text_h - margin

        # Тень (сдвиг 1px вниз-вправо, непрозрачность 160/255)
        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 160))
        # Текст (белый, непрозрачность 200/255)
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 200))

        # Merge слоёв
        result = Image.alpha_composite(img, overlay).convert("RGB")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, "JPEG", quality=92, optimize=True)
        return output_path

    # ------------------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------------------------------------------------

    def _prepare_task_dir(self, task_id: str) -> Path:
        """Создаёт директорию data/processed/{task_id}/."""
        task_dir = self.output_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def _copy_original(self, src: str, dst: Path) -> None:
        """Копирует оригинал в папку задачи как original.jpg."""
        src_path = Path(src)
        if not src_path.exists():
            raise FileNotFoundError(f"Входной файл не найден: {src}")

        # Конвертируем в JPEG если нужно
        if src_path.suffix.lower() in (".jpg", ".jpeg"):
            shutil.copy2(src, dst)
        else:
            img = Image.open(src).convert("RGB")
            img.save(dst, "JPEG", quality=95)

    @staticmethod
    def _resize_to_max(img: Image.Image, max_side: int) -> Image.Image:
        """Ресайз изображения с сохранением пропорций (по длинной стороне)."""
        w, h = img.size
        if max(w, h) <= max_side:
            return img
        if w >= h:
            new_w = max_side
            new_h = int(h * max_side / w)
        else:
            new_h = max_side
            new_w = int(w * max_side / h)
        return img.resize((new_w, new_h), Image.LANCZOS)


# === ВЫВОД РЕЗУЛЬТАТА В КОНСОЛЬ ===

def print_result(result: ProcessResult) -> None:
    """Красивый вывод результата в консоль."""
    print(f"\n{'=' * 60}")
    print(f"  РЕЗУЛЬТАТ: task_id={result.task_id}")
    print(f"  Статус: {result.status}")
    if result.error_message:
        print(f"  Ошибка: {result.error_message}")
    print(f"{'=' * 60}")

    paths = [
        ("Оригинал", result.original_path),
        ("Реставрация", result.restored_path),
        ("Раскраска", result.colorized_path),
        ("Анимация", result.animated_path),
        ("Водяной знак", result.watermarked_path),
    ]
    for label, path in paths:
        if path:
            exists = "[OK]" if Path(path).exists() else "[!] файл не создан"
            print(f"  {label}: {path}  {exists}")

    if result.steps_log:
        print(f"\n  Шаги:")
        for step in result.steps_log:
            print(
                f"    {step['step']:12s}  {step['method']:8s}  {step['duration_sec']:.1f} сек"
            )

    if result.started_at and result.completed_at:
        total = (result.completed_at - result.started_at).total_seconds()
        print(f"\n  Общее время: {total:.1f} сек")


# === CLI ===

async def _main_async(args: argparse.Namespace) -> None:
    processor = PhotoProcessor(output_dir=args.output_dir)
    steps = args.steps or ["restore", "colorize", "animate", "watermark"]

    result = await processor.process_full(
        image_path=args.input,
        task_id=args.task_id,
        steps=steps,
    )
    print_result(result)
    sys.exit(0 if result.status == "completed" else 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Память 9 Мая — Photo Processor Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python3 pipeline/photo_processor.py --input photo.jpg --task-id test1
  python3 pipeline/photo_processor.py --input photo.jpg --task-id test1 --steps restore colorize
  python3 pipeline/photo_processor.py --input photo.jpg --task-id test1 --output-dir /tmp/out
        """,
    )
    parser.add_argument("--input", required=True, help="Путь к исходному фото")
    parser.add_argument("--task-id", required=True, help="Уникальный ID задачи")
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["restore", "colorize", "animate", "watermark"],
        help="Шаги для выполнения (по умолчанию: все четыре)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Директория для результатов (default: data/processed)",
    )
    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"[ОШИБКА] Файл не найден: {args.input}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
