"""
/quiz handler — 10-question WWII quiz with FSM, shuffled answers, score tracking.
"""
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.database import save_quiz_result

logger = logging.getLogger(__name__)
router = Router(name="quiz")


@dataclass
class Question:
    text: str
    correct: str
    wrong: list[str]


# 10 historically accurate questions about the Great Patriotic War
RAW_QUESTIONS: list[Question] = [
    Question(
        text="В какой день началась Великая Отечественная война?",
        correct="22 июня 1941 года",
        wrong=["1 сентября 1939 года", "9 мая 1945 года", "22 июня 1940 года"],
    ),
    Question(
        text="Сколько дней длилась блокада Ленинграда?",
        correct="872 дня",
        wrong=["500 дней", "1000 дней", "365 дней"],
    ),
    Question(
        text="Кто командовал Парадом Победы на Красной площади 24 июня 1945 года?",
        correct="Маршал Рокоссовский",
        wrong=["Маршал Жуков", "Маршал Конев", "Маршал Василевский"],
    ),
    Question(
        text="Как называлось крупнейшее танковое сражение Второй мировой войны?",
        correct="Курская битва",
        wrong=["Битва за Москву", "Сталинградская битва", "Операция «Багратион»"],
    ),
    Question(
        text="Какой город-герой расположен на берегах Волги и стал символом переломной битвы?",
        correct="Сталинград",
        wrong=["Ленинград", "Севастополь", "Одесса"],
    ),
    Question(
        text="Какую советскую республику освобождала операция «Багратион» (1944)?",
        correct="Белоруссию",
        wrong=["Украину", "Прибалтику", "Молдавию"],
    ),
    Question(
        text="Когда советские воины водрузили Знамя Победы над Рейхстагом?",
        correct="30 апреля 1945 года",
        wrong=["9 мая 1945 года", "1 мая 1945 года", "2 мая 1945 года"],
    ),
    Question(
        text="Кто написал слова знаменитой военной песни «Священная война»?",
        correct="Василий Лебедев-Кумач",
        wrong=["Михаил Исаковский", "Константин Симонов", "Алексей Сурков"],
    ),
    Question(
        text="Сколько дней длилась Великая Отечественная война?",
        correct="1418 дней",
        wrong=["1200 дней", "1500 дней", "900 дней"],
    ),
    Question(
        text="Кто из советских маршалов принял капитуляцию Германии 8 мая 1945 года?",
        correct="Маршал Жуков",
        wrong=["Маршал Рокоссовский", "Маршал Конев", "Маршал Василевский"],
    ),
]


class QuizStates(StatesGroup):
    answering = State()


@dataclass
class QuizSession:
    questions: list[Question]
    current: int = 0
    score: int = 0
    # shuffled answer lists per question index
    shuffled_answers: dict[int, list[str]] = field(default_factory=dict)

    def current_question(self) -> Optional[Question]:
        if self.current < len(self.questions):
            return self.questions[self.current]
        return None

    def answers_for(self, idx: int) -> list[str]:
        if idx not in self.shuffled_answers:
            q = self.questions[idx]
            answers = [q.correct] + q.wrong
            random.shuffle(answers)
            self.shuffled_answers[idx] = answers
        return self.shuffled_answers[idx]


def _make_keyboard(answers: list[str], q_idx: int) -> InlineKeyboardMarkup:
    """Build 2-column inline keyboard with answer options."""
    buttons: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(answers), 2):
        row = []
        for answer in answers[i:i + 2]:
            row.append(InlineKeyboardButton(
                text=answer,
                callback_data=f"quiz:{q_idx}:{answer}",
            ))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _score_message(score: int, total: int) -> str:
    pct = score / total if total else 0
    if score == total:
        medal = "Блестящий результат! Вы отлично знаете историю Великой Победы."
    elif pct >= 0.8:
        medal = "Очень хорошо! Вы хорошо знаете историю Великой Отечественной войны."
    elif pct >= 0.5:
        medal = "Неплохо. Есть что узнать — история войны богата и важна."
    else:
        medal = "Стоит углубиться в историю. Помните: знать — значит чтить."
    return (
        f"<b>Результат: {score} из {total}</b>\n\n"
        f"{medal}"
    )


@router.message(Command("quiz"))
async def cmd_quiz(message: Message, state: FSMContext) -> None:
    questions = RAW_QUESTIONS.copy()
    random.shuffle(questions)
    session = QuizSession(questions=questions)

    await state.set_state(QuizStates.answering)
    await state.update_data(session=session.__dict__, shuffled_answers=session.shuffled_answers)

    await _send_question(message, session)


async def _send_question(target: Message | CallbackQuery, session: QuizSession) -> None:
    q = session.current_question()
    if q is None:
        return

    answers = session.answers_for(session.current)
    keyboard = _make_keyboard(answers, session.current)
    text = (
        f"<b>Вопрос {session.current + 1} из {len(session.questions)}</b>\n\n"
        f"{q.text}"
    )

    if isinstance(target, CallbackQuery) and target.message:
        await target.message.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


@router.callback_query(QuizStates.answering, F.data.startswith("quiz:"))
async def handle_answer(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    raw = data.get("session", {})
    shuffled = data.get("shuffled_answers", {})

    # Reconstruct session
    session = QuizSession(
        questions=[Question(**q) if isinstance(q, dict) else q for q in raw.get("questions", [])],
        current=raw.get("current", 0),
        score=raw.get("score", 0),
        shuffled_answers={int(k): v for k, v in shuffled.items()},
    )

    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer()
        return

    chosen_answer = parts[2]
    q = session.current_question()
    if q is None:
        await callback.answer()
        return

    is_correct = chosen_answer == q.correct
    if is_correct:
        session.score += 1
        feedback = "Верно."
    else:
        feedback = f"Неверно. Правильный ответ: {q.correct}."

    session.current += 1

    # Persist updated session
    await state.update_data(
        session={
            "questions": [q.__dict__ for q in session.questions],
            "current": session.current,
            "score": session.score,
        },
        shuffled_answers={str(k): v for k, v in session.shuffled_answers.items()},
    )

    if session.current >= len(session.questions):
        # Quiz complete
        await state.clear()
        user = callback.from_user
        try:
            await save_quiz_result(
                user_id=user.id if user else None,
                user_name=user.full_name if user else None,
                score=session.score,
                total=len(session.questions),
            )
        except Exception:
            logger.exception("Failed to save quiz result")

        result_text = (
            f"{feedback}\n\n"
            + _score_message(session.score, len(session.questions))
        )
        if callback.message:
            await callback.message.edit_text(result_text, reply_markup=None)
        await callback.answer()
        return

    # Next question
    await callback.answer(feedback)
    await _send_question(callback, session)
