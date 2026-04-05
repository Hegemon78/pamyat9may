"""
/start handler — welcome message, deep link routing, command overview.
"""
import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from services.database import upsert_user

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_TEXT = """
<b>Память Победы</b>

Этот бот создан в память о ветеранах Великой Отечественной войны — тех, кто сражался, трудился и выжил, чтобы мы могли жить.

<b>Что можно сделать:</b>

/quiz — пройти викторину о ВОВ и проверить свои знания

/story — рассказать о своём герое: деде, прадеде, родственнике-участнике войны

/wall — прочитать истории других людей о ветеранах

/stats — посмотреть общую статистику стены памяти

Ваши воспоминания — это живая история. Поделитесь ею.
""".strip()

WALL_REDIRECT = """
Хотите поделиться историей о своём герое?

Введите /story, и я помогу вам рассказать о нём.
""".strip()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user:
        try:
            await upsert_user(
                user_id=user.id,
                first_name=user.first_name or "",
                username=user.username,
            )
        except Exception:
            logger.exception("Failed to upsert user %s", user.id)

    # Handle deep link: /start wall
    args = message.text.split(maxsplit=1)[1] if message.text and " " in message.text else ""
    if args.strip().lower() == "wall":
        await message.answer(WALL_REDIRECT)
        return

    await message.answer(WELCOME_TEXT)
