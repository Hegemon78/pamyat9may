"""
/story — submit memorial story via FSM (3 steps).
/wall  — browse approved stories with pagination.
/stats — aggregated statistics.
/cancel — abort any active FSM state.
"""
import logging
import math

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.database import get_stats, get_stories, get_story_count, save_story

logger = logging.getLogger(__name__)
router = Router(name="story")

PAGE_SIZE = 10


class StoryStates(StatesGroup):
    waiting_hero_name = State()
    waiting_text = State()
    waiting_photo = State()


# ---------------------------------------------------------------------------
# /cancel
# ---------------------------------------------------------------------------

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("Нет активного действия для отмены.")
        return
    await state.clear()
    await message.answer("Действие отменено.")


# ---------------------------------------------------------------------------
# /story — FSM flow
# ---------------------------------------------------------------------------

@router.message(Command("story"))
async def cmd_story(message: Message, state: FSMContext) -> None:
    await state.set_state(StoryStates.waiting_hero_name)
    await message.answer(
        "<b>Расскажите о своём герое</b>\n\n"
        "Напишите имя человека, о котором хотите рассказать.\n"
        "Это может быть дед, прадед, другой родственник или близкий человек.\n\n"
        "Для отмены введите /cancel"
    )


@router.message(StoryStates.waiting_hero_name, F.text)
async def process_hero_name(message: Message, state: FSMContext) -> None:
    hero_name = (message.text or "").strip()
    if len(hero_name) > 200:
        await message.answer("Имя слишком длинное. Пожалуйста, сократите до 200 символов.")
        return

    await state.update_data(hero_name=hero_name)
    await state.set_state(StoryStates.waiting_text)
    await message.answer(
        f"<b>{hero_name}</b> — запомним это имя.\n\n"
        "Теперь напишите историю. Расскажите, кем он был, где воевал или трудился, "
        "что вы о нём помните.\n\n"
        "Нет нормы по объёму — пишите столько, сколько хочется."
    )


@router.message(StoryStates.waiting_text, F.text)
async def process_story_text(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("История не может быть пустой. Пожалуйста, напишите хоть несколько слов.")
        return
    if len(text) > 4000:
        await message.answer(
            f"История слишком длинная ({len(text)} символов). "
            "Пожалуйста, сократите до 4000 символов."
        )
        return

    await state.update_data(text=text)
    await state.set_state(StoryStates.waiting_photo)
    await message.answer(
        "Если у вас есть фотография этого человека — отправьте её.\n\n"
        "Если фотографии нет или вы не хотите добавлять — введите /skip"
    )


@router.message(StoryStates.waiting_photo, Command("skip"))
async def process_photo_skip(message: Message, state: FSMContext) -> None:
    await _finalize_story(message, state, photo_url=None)


@router.message(StoryStates.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext) -> None:
    # Store the file_id of the largest photo size as photo_url reference
    photo = message.photo[-1] if message.photo else None
    photo_url = photo.file_id if photo else None
    await _finalize_story(message, state, photo_url=photo_url)


@router.message(StoryStates.waiting_photo)
async def process_photo_invalid(message: Message, _state: FSMContext) -> None:
    await message.answer(
        "Пожалуйста, отправьте фотографию или введите /skip для пропуска."
    )


async def _finalize_story(message: Message, state: FSMContext, photo_url: str | None) -> None:
    data = await state.get_data()
    hero_name: str = data.get("hero_name", "")
    text: str = data.get("text", "")

    user = message.from_user
    try:
        story_id = await save_story(
            user_id=user.id if user else None,
            user_name=user.full_name if user else None,
            hero_name=hero_name or None,
            text=text,
            photo_url=photo_url,
        )
        logger.info("Story saved: id=%s hero=%r user=%s", story_id, hero_name, user.id if user else None)
    except Exception:
        logger.exception("Failed to save story")
        await message.answer("Произошла ошибка при сохранении истории. Попробуйте позже.")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        "Спасибо. История сохранена.\n\n"
        f"<b>{hero_name}</b> теперь на стене памяти — её смогут прочитать все, "
        "кто приходит сюда помнить.\n\n"
        "Посмотреть все истории: /wall"
    )


# ---------------------------------------------------------------------------
# /wall — paginated story feed
# ---------------------------------------------------------------------------

def _wall_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup | None:
    if total_pages <= 1:
        return None
    buttons: list[InlineKeyboardButton] = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="Назад", callback_data=f"wall:{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Вперёд", callback_data=f"wall:{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons]) if buttons else None


def _format_story(story: dict, index: int) -> str:
    hero = story.get("hero_name") or "Неизвестный герой"
    author = story.get("user_name") or "Аноним"
    text = story.get("text") or ""
    # Truncate long texts for the wall view
    if len(text) > 300:
        text = text[:297] + "..."
    return f"<b>{index}. {hero}</b>\n{text}\n<i>— {author}</i>"


async def _send_wall_page(target: Message | CallbackQuery, page: int) -> None:
    total = await get_story_count(approved_only=True)
    if total == 0:
        text = "Стена памяти пока пуста. Будьте первым — введите /story"
        if isinstance(target, CallbackQuery) and target.message:
            await target.message.edit_text(text)
        else:
            await target.answer(text)
        return

    total_pages = math.ceil(total / PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    stories = await get_stories(limit=PAGE_SIZE, offset=page * PAGE_SIZE, approved_only=True)
    start_idx = page * PAGE_SIZE + 1

    parts = [f"<b>Стена памяти</b> (стр. {page + 1} из {total_pages}, всего {total})\n"]
    for i, story in enumerate(stories):
        parts.append(_format_story(story, start_idx + i))

    text = "\n\n".join(parts)
    keyboard = _wall_keyboard(page, total_pages)

    if isinstance(target, CallbackQuery) and target.message:
        await target.message.edit_text(text, reply_markup=keyboard)
        await target.answer()
    else:
        await target.answer(text, reply_markup=keyboard)


@router.message(Command("wall"))
async def cmd_wall(message: Message) -> None:
    await _send_wall_page(message, page=0)


@router.callback_query(F.data.startswith("wall:"))
async def handle_wall_page(callback: CallbackQuery) -> None:
    try:
        page = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        page = 0
    await _send_wall_page(callback, page)


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    try:
        stats = await get_stats()
    except Exception:
        logger.exception("Failed to load stats")
        await message.answer("Не удалось загрузить статистику. Попробуйте позже.")
        return

    await message.answer(
        "<b>Статистика стены памяти</b>\n\n"
        f"Историй: {stats['stories']}\n"
        f"Участников: {stats['users']}\n"
        f"Прохождений викторины: {stats['quiz_completions']}"
    )
