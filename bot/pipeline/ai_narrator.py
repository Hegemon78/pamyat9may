#!/usr/bin/env python3
"""
AI Narrator — генератор нарратива боевого пути для сервиса "Память 9 Мая".

Pipeline: search_results (JSON из research_pipeline.py) → анализ (Haiku) → нарратив (Sonnet).

Использование:
    python3 pipeline/ai_narrator.py --input data/иванов_пётр_results.json --name "Иванов Пётр Иванович"
    python3 pipeline/ai_narrator.py --input data/иванов_пётр_results.json --name "Иванов Пётр Иванович" --offline
"""

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass, field

import aiohttp

# === Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_narrator")

# === OpenRouter config ===
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
HAIKU_MODEL = "anthropic/claude-3-5-haiku-20241022"
SONNET_MODEL = "anthropic/claude-sonnet-4-20250514"

REQUEST_TIMEOUT = 30
RETRY_DELAYS = (1, 2, 4)  # exponential backoff (сек)

# === Prompts ===
ANALYSIS_SYSTEM_PROMPT = """Ты — военный историк-архивист. Анализируешь данные из архивных баз ВОВ и выделяешь ключевые факты."""

ANALYSIS_USER_PROMPT = """Проанализируй данные из архивных баз ВОВ по конкретному ветерану.

Данные:
{json_results}

Задача:
1. Определи, какие записи относятся к одному человеку (дедупликация по ФИО, году рождения, части). Используй вердикты: НАШ — точное совпадение, ВОЗМОЖНО — вероятное, НЕ НАШ — однофамилец.
2. Выдели ключевые факты: звание, воинская часть, даты службы, награды, судьба.
3. Оцени достоверность итогового профиля: "high" (есть запись НАШ или совпадают отчество+год), "medium" (только ВОЗМОЖНО, данных достаточно), "low" (мало данных или только однофамильцы).
4. Составь хронологию событий на основе дат документов.
5. Собери список архивных источников (архив, фонд, опись — если есть).

Отвечай строго в формате JSON:
{{
  "primary_person": {{
    "full_name": "...",
    "birth_year": "...",
    "rank": "...",
    "unit": "...",
    "fate": "выжил / погиб / неизвестно"
  }},
  "awards": [
    {{
      "name": "...",
      "date": "...",
      "awarded_by": "...",
      "document_url": "..."
    }}
  ],
  "timeline": [
    {{
      "date": "...",
      "event": "...",
      "source": "..."
    }}
  ],
  "sources": ["..."],
  "confidence": "high | medium | low",
  "confidence_reason": "...",
  "deduplication_note": "..."
}}"""

NARRATIVE_SYSTEM_PROMPT = """Ты — автор мемориальных текстов. Пишешь уважительные, сдержанные истории боевого пути ветеранов Великой Отечественной войны на основе архивных данных."""

NARRATIVE_USER_PROMPT = """На основе анализа архивных данных напиши историю боевого пути ветерана.

Анализ:
{analysis_json}

Имя ветерана: {hero_name}

Требования:
- 2-3 абзаца, 150-250 слов
- Сдержанный, уважительный тон — без пафоса и излишней патетики
- Опирайся только на факты из архивов, НЕ додумывай детали
- Если данных мало — честно укажи: "подробности боевого пути требуют дополнительного исследования"
- В конце укажи архивные источники (архив, фонд, опись — если известны)
- Формат: чистый текст, без markdown"""


@dataclass
class NarrativeResult:
    """Результат AI-генерации нарратива боевого пути."""

    title: str
    """Заголовок: "Боевой путь Иванова Петра Ивановича"."""

    summary: str
    """2-3 абзаца связной истории."""

    timeline: list[dict] = field(default_factory=list)
    """Хронология событий: [{date, event, source}]."""

    awards: list[dict] = field(default_factory=list)
    """Награды: [{name, date, description, document}]."""

    service_info: dict = field(default_factory=dict)
    """Данные о службе: {rank, unit, fate, birth_year, ...}."""

    sources: list[str] = field(default_factory=list)
    """Архивные источники: ["ЦАМО, Ф. 33, Оп. 690155", ...]."""

    confidence: str = "low"
    """Достоверность: "high" | "medium" | "low"."""

    raw_analysis: str = ""
    """Сырой JSON-ответ Claude Haiku для отладки."""


class AINarrator:
    """AI-генератор нарратива боевого пути ветерана ВОВ."""

    def __init__(self, api_key: str | None = None) -> None:
        """
        Инициализация нарратора.

        Args:
            api_key: ключ OpenRouter API. Если не передан —
                     берётся из переменной окружения OPENROUTER_API_KEY.
        """
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self._api_key:
            logger.warning(
                "OPENROUTER_API_KEY не задан — AI-функции недоступны. "
                "Используй generate_narrative_offline() или передай api_key."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_narrative(
        self, search_results: dict, hero_name: str
    ) -> NarrativeResult:
        """
        Полный AI-pipeline: анализ данных → построение нарратива.

        Args:
            search_results: JSON из research_pipeline.py (awards, losses, query, ...).
            hero_name: полное имя ветерана, например "Иванов Пётр Иванович".

        Returns:
            NarrativeResult с заполненными полями.

        Raises:
            RuntimeError: если API-ключ не задан.
        """
        if not self._api_key:
            raise RuntimeError(
                "API-ключ OpenRouter не задан. "
                "Используй generate_narrative_offline() или задай OPENROUTER_API_KEY."
            )

        logger.info("Шаг 1/2: анализ данных через Claude Haiku...")
        analysis = await self._analyze(search_results)
        logger.info("Шаг 2/2: генерация нарратива через Claude Sonnet...")
        narrative_text = await self._build_narrative(analysis, hero_name)

        timeline = self._extract_timeline(analysis)
        awards = self._extract_awards(analysis)
        service_info = self._extract_service_info(analysis)
        sources = analysis.get("sources", [])
        confidence = analysis.get("confidence", "low")

        return NarrativeResult(
            title=f"Боевой путь {hero_name}",
            summary=narrative_text,
            timeline=timeline,
            awards=awards,
            service_info=service_info,
            sources=sources,
            confidence=confidence,
            raw_analysis=json.dumps(analysis, ensure_ascii=False, indent=2),
        )

    def generate_narrative_offline(
        self, search_results: dict, hero_name: str
    ) -> NarrativeResult:
        """
        Шаблонный fallback без AI — работает без API-ключа.

        Собирает текст из имеющихся данных по шаблону.

        Args:
            search_results: JSON из research_pipeline.py.
            hero_name: полное имя ветерана.

        Returns:
            NarrativeResult на основе шаблона.
        """
        logger.info("Offline-режим: генерация шаблонного нарратива...")

        awards_all = search_results.get("awards", [])
        losses = search_results.get("losses", [])

        # Фильтр: только НАШ и ВОЗМОЖНО
        relevant = [
            r for r in awards_all if r.get("verdict") in ("НАШ", "ВОЗМОЖНО")
        ]

        # Извлекаем первичные данные из лучшей записи
        primary = self._best_record(relevant) or {}
        rank = primary.get("rank", "")
        unit = primary.get("awarded_by", "")
        birth_date = primary.get("birth_date", "")
        birth_year = self._parse_year(birth_date) if birth_date else ""

        # Список наград (дедупликация по названию)
        seen_awards: set[str] = set()
        awards_list: list[dict] = []
        for r in relevant:
            award_name = r.get("award", "")
            if award_name and award_name not in seen_awards:
                seen_awards.add(award_name)
                awards_list.append(
                    {
                        "name": award_name,
                        "date": r.get("date", ""),
                        "description": "",
                        "document": r.get("award_url", ""),
                    }
                )

        # Список источников
        sources: list[str] = []
        seen_archives: set[str] = set()
        for r in relevant:
            arch = r.get("archive", "")
            if arch and arch not in seen_archives:
                seen_archives.add(arch)
                sources.append(arch)

        # Судьба
        fate_note = ""
        if losses:
            loss = losses[0]
            cause = loss.get("cause", "выбыл из строя")
            date_loss = loss.get("date_loss", "")
            place = loss.get("place_loss", "")
            fate_note = f" {cause}"
            if date_loss:
                fate_note += f" {date_loss}"
            if place:
                fate_note += f" ({place})"
            fate_note += "."

        # Составляем текст
        parts: list[str] = []

        # Блок 1: персональные данные
        intro_parts = [hero_name]
        if birth_year:
            intro_parts.append(f"{birth_year} года рождения")
        intro = ", ".join(intro_parts) + "."

        service_parts: list[str] = []
        if rank:
            service_parts.append(f"в звании {rank}")
        if unit:
            service_parts.append(f"в составе {unit}")
        service_line = (
            f"Проходил службу {' '.join(service_parts)}."
            if service_parts
            else "Сведения о месте службы требуют дополнительного исследования."
        )

        parts.append(f"{intro} {service_line}")

        # Блок 2: награды
        if awards_list:
            names = ", ".join(a["name"] for a in awards_list)
            parts.append(
                f"За время Великой Отечественной войны был отмечен следующими "
                f"наградами: {names}."
            )
        else:
            parts.append(
                "Наградные документы в открытых архивных базах не обнаружены — "
                "это не исключает участия в боевых действиях."
            )

        # Блок 3: судьба и источники
        if fate_note:
            parts.append(fate_note.strip())

        if sources:
            src_line = ", ".join(sources)
            parts.append(f"Источники: {src_line}.")
        else:
            parts.append(
                "Для уточнения сведений рекомендуется запрос в ЦАМО (г. Подольск)."
            )

        summary = "\n\n".join(parts)

        # Хронология (из дат наград)
        timeline = [
            {
                "date": r.get("date", ""),
                "event": f"Награждён: {r.get('award', '')}",
                "source": r.get("archive", ""),
            }
            for r in relevant
            if r.get("date") and r.get("award")
        ]
        # Сортировка по дате (YYYY или __.__.YYYY)
        timeline.sort(key=lambda x: self._sort_date_key(x.get("date", "")))

        confidence = "medium" if relevant else "low"

        return NarrativeResult(
            title=f"Боевой путь {hero_name}",
            summary=summary,
            timeline=timeline,
            awards=awards_list,
            service_info={
                "rank": rank,
                "unit": unit,
                "birth_year": birth_year,
                "fate": "погиб" if losses else "неизвестно",
            },
            sources=sources,
            confidence=confidence,
            raw_analysis="",
        )

    # ------------------------------------------------------------------
    # Private: AI pipeline
    # ------------------------------------------------------------------

    async def _analyze(self, search_results: dict) -> dict:
        """
        Шаг 1: Claude Haiku анализирует данные, выделяет факты.

        Отправляет весь JSON из research_pipeline.py.
        Возвращает структурированный dict с полями primary_person, awards,
        timeline, sources, confidence.
        """
        # Ограничиваем объём: оставляем только НАШ + ВОЗМОЖНО (max 50 записей)
        filtered = self._filter_results_for_prompt(search_results)
        json_results = json.dumps(filtered, ensure_ascii=False, indent=2)

        prompt = ANALYSIS_USER_PROMPT.format(json_results=json_results)

        raw = await self._call_api(
            model=HAIKU_MODEL,
            system=ANALYSIS_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=2000,
        )

        # Парсим JSON из ответа (Claude может обернуть в ```json ... ```)
        analysis = self._parse_json_response(raw)
        logger.debug("Анализ получен: confidence=%s", analysis.get("confidence"))
        return analysis

    async def _build_narrative(self, analysis: dict, hero_name: str) -> str:
        """
        Шаг 2: Claude Sonnet пишет связную мемориальную историю.

        Args:
            analysis: результат _analyze().
            hero_name: полное имя ветерана.

        Returns:
            Текст нарратива (чистый текст, без markdown).
        """
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
        prompt = NARRATIVE_USER_PROMPT.format(
            analysis_json=analysis_json,
            hero_name=hero_name,
        )

        narrative = await self._call_api(
            model=SONNET_MODEL,
            system=NARRATIVE_SYSTEM_PROMPT,
            user=prompt,
            max_tokens=1000,
        )
        return narrative.strip()

    # ------------------------------------------------------------------
    # Private: HTTP
    # ------------------------------------------------------------------

    async def _call_api(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 1500,
    ) -> str:
        """
        Отправить запрос к OpenRouter API с retry (exponential backoff).

        Args:
            model: идентификатор модели.
            system: системный промпт.
            user: пользовательский промпт.
            max_tokens: максимальное число токенов в ответе.

        Returns:
            Текст ответа модели.

        Raises:
            RuntimeError: если все попытки исчерпаны.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://pamyat9may.ru",
            "X-Title": "Память 9 Мая",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        last_error: Exception | None = None

        for attempt, delay in enumerate(RETRY_DELAYS, start=1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        OPENROUTER_URL, headers=headers, json=payload
                    ) as resp:
                        if resp.status in (429, 500, 502, 503, 504):
                            body = await resp.text()
                            logger.warning(
                                "Попытка %d/%d: HTTP %d — жду %d сек. Ответ: %s",
                                attempt,
                                len(RETRY_DELAYS),
                                resp.status,
                                delay,
                                body[:200],
                            )
                            await asyncio.sleep(delay)
                            continue

                        if resp.status != 200:
                            body = await resp.text()
                            raise RuntimeError(
                                f"OpenRouter вернул {resp.status}: {body[:300]}"
                            )

                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]

            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                logger.warning(
                    "Попытка %d/%d: сетевая ошибка (%s) — жду %d сек.",
                    attempt,
                    len(RETRY_DELAYS),
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"OpenRouter: все {len(RETRY_DELAYS)} попытки исчерпаны. "
            f"Последняя ошибка: {last_error}"
        )

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------

    def _filter_results_for_prompt(self, search_results: dict) -> dict:
        """
        Подготовить данные для промпта: только НАШ + ВОЗМОЖНО, max 50 наград.

        Уменьшаем объём JSON, чтобы не превышать контекст Haiku.
        """
        awards_all = search_results.get("awards", [])
        relevant = [
            r for r in awards_all if r.get("verdict") in ("НАШ", "ВОЗМОЖНО")
        ]
        # Если совсем нет релевантных — берём первые 10 с любым вердиктом
        if not relevant:
            relevant = awards_all[:10]

        return {
            "query": search_results.get("query", {}),
            "awards": relevant[:50],
            "losses": search_results.get("losses", [])[:10],
            "foreign_awards": search_results.get("foreign_awards", [])[:10],
            "total_awards": search_results.get("total_awards", 0),
            "total_losses": search_results.get("total_losses", 0),
        }

    @staticmethod
    def _parse_json_response(raw: str) -> dict:
        """
        Извлечь JSON из ответа Claude (который может обернуть его в ```json ... ```).
        """
        text = raw.strip()
        # Убираем markdown-блоки
        if text.startswith("```"):
            lines = text.splitlines()
            # Снимаем первую и последнюю строки-декораторы
            inner = [
                l for l in lines[1:]
                if not l.strip().startswith("```")
            ]
            text = "\n".join(inner).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "Не удалось распарсить JSON из ответа Claude. "
                "Возвращаю пустой dict. Ответ: %s",
                raw[:300],
            )
            return {}

    @staticmethod
    def _extract_timeline(analysis: dict) -> list[dict]:
        """Извлечь хронологию из результата _analyze()."""
        raw = analysis.get("timeline", [])
        if not isinstance(raw, list):
            return []
        return [
            {
                "date": item.get("date", ""),
                "event": item.get("event", ""),
                "source": item.get("source", ""),
            }
            for item in raw
            if isinstance(item, dict)
        ]

    @staticmethod
    def _extract_awards(analysis: dict) -> list[dict]:
        """Извлечь список наград из результата _analyze()."""
        raw = analysis.get("awards", [])
        if not isinstance(raw, list):
            return []
        return [
            {
                "name": item.get("name", ""),
                "date": item.get("date", ""),
                "description": item.get("description", ""),
                "document": item.get("document_url", ""),
            }
            for item in raw
            if isinstance(item, dict)
        ]

    @staticmethod
    def _extract_service_info(analysis: dict) -> dict:
        """Извлечь данные о службе из результата _analyze()."""
        primary = analysis.get("primary_person", {})
        if not isinstance(primary, dict):
            return {}
        return {
            "rank": primary.get("rank", ""),
            "unit": primary.get("unit", ""),
            "birth_year": primary.get("birth_year", ""),
            "fate": primary.get("fate", "неизвестно"),
        }

    @staticmethod
    def _best_record(records: list[dict]) -> dict | None:
        """
        Выбрать наиболее информативную запись из списка.

        Приоритет: НАШ > ВОЗМОЖНО, затем по наличию звания.
        """
        if not records:
            return None
        verdict_order = {"НАШ": 0, "ВОЗМОЖНО": 1, "НЕ НАШ": 2}
        return sorted(
            records,
            key=lambda r: (verdict_order.get(r.get("verdict", ""), 3), not r.get("rank")),
        )[0]

    @staticmethod
    def _parse_year(birth_date: str) -> str:
        """Извлечь год из строки вида '__.__.1915' или '25.06.1923'."""
        if not birth_date:
            return ""
        parts = birth_date.split(".")
        if parts:
            year = parts[-1]
            if year.isdigit() and len(year) == 4:
                return year
        return ""

    @staticmethod
    def _sort_date_key(date_str: str) -> str:
        """
        Ключ сортировки для дат вида '__.__.1943', '15.02.1945', '1945-05-09'.

        Преобразует к виду YYYY-MM-DD для лексикографической сортировки.
        """
        if not date_str:
            return "9999"
        parts = date_str.split(".")
        if len(parts) == 3:
            day, month, year = parts
            day = "01" if not day.isdigit() else day.zfill(2)
            month = "01" if not month.isdigit() else month.zfill(2)
            year = year if year.isdigit() else "9999"
            return f"{year}-{month}-{day}"
        return date_str


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------


def _print_result(result: NarrativeResult) -> None:
    """Вывести NarrativeResult в консоль в читаемом виде."""
    print("\n" + "=" * 70)
    print(f"  {result.title}")
    print("=" * 70)
    print(f"\n  Достоверность: {result.confidence.upper()}")

    if result.service_info:
        si = result.service_info
        print("\n  Данные о службе:")
        if si.get("rank"):
            print(f"    Звание: {si['rank']}")
        if si.get("unit"):
            print(f"    Часть: {si['unit']}")
        if si.get("birth_year"):
            print(f"    Год рождения: {si['birth_year']}")
        if si.get("fate"):
            print(f"    Судьба: {si['fate']}")

    if result.awards:
        print(f"\n  Награды ({len(result.awards)}):")
        for a in result.awards:
            line = f"    - {a['name']}"
            if a.get("date"):
                line += f" ({a['date']})"
            print(line)

    if result.timeline:
        print(f"\n  Хронология ({len(result.timeline)} событий):")
        for t in result.timeline[:10]:
            print(f"    {t.get('date', '?')}: {t.get('event', '')}")

    print("\n  Нарратив:")
    print("-" * 70)
    print(result.summary)
    print("-" * 70)

    if result.sources:
        print(f"\n  Источники: {', '.join(result.sources)}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Память 9 Мая — AI Narrator: генератор нарратива боевого пути"
    )
    parser.add_argument(
        "--input", required=True, help="Путь к JSON-файлу из research_pipeline.py"
    )
    parser.add_argument(
        "--name",
        required=True,
        help='Полное имя ветерана, например "Иванов Пётр Иванович"',
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Шаблонный режим без AI (не требует API-ключа)",
    )
    parser.add_argument(
        "--output",
        help="Путь для сохранения результата в JSON (опционально)",
    )
    parser.add_argument(
        "--api-key",
        help="OpenRouter API-ключ (альтернатива переменной OPENROUTER_API_KEY)",
    )
    args = parser.parse_args()

    # Загружаем данные
    with open(args.input, encoding="utf-8") as f:
        search_results = json.load(f)

    narrator = AINarrator(api_key=args.api_key)

    if args.offline:
        result = narrator.generate_narrative_offline(search_results, args.name)
    else:
        result = asyncio.run(narrator.generate_narrative(search_results, args.name))

    _print_result(result)

    if args.output:
        output_data = {
            "title": result.title,
            "summary": result.summary,
            "timeline": result.timeline,
            "awards": result.awards,
            "service_info": result.service_info,
            "sources": result.sources,
            "confidence": result.confidence,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"  Результат сохранён: {args.output}")


if __name__ == "__main__":
    main()
