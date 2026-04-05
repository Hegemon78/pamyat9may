#!/usr/bin/env python3
"""
Research Pipeline — ядро сервиса "Память 9 Мая".

Оркестратор: ФИО → ES API → анализ → вердикты → отчёт.

Использование:
    python3 pipeline/research_pipeline.py --last-name "Иванов" --first-name "Пётр"
    python3 pipeline/research_pipeline.py --last-name "Бурмистров" --first-name "Прокофий" --middle-name "Иосифович" --birth-year 1913
"""

import json
import subprocess
import tempfile
import argparse
import os
from pathlib import Path
from typing import Any


# === ES API CONFIG ===
ES_BASE_URL = "https://cdn.pamyat-naroda.ru/ind"
ES_HEADERS = {
    "Content-Type": "text/plain; charset=UTF-8",
    "Referer": "https://pamyat-naroda.ru/heroes/",
}

# Рабочие индексы (проверено 15.03.2026)
INDICES = [
    {"index": "podvig", "type": "nagrada_kartoteka", "label": "Наградные карточки", "records": "21.8M"},
    {"index": "podvig", "type": "nagrada_in_kartoteka", "label": "Иностранные награды", "records": "173K"},
    {"index": "memorial", "type": "chelovek_donesenie", "label": "Донесения о потерях", "records": "~135 в ES"},
]


def es_search(index: str, doc_type: str, query: dict, size: int = 50) -> dict:
    """Поиск через ES API pamyat-naroda.ru (curl, т.к. Node.js TLS не работает)."""
    url = f"{ES_BASE_URL}/{index}/{doc_type}/_search"
    body = json.dumps({"query": query, "size": size})

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(body)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [
                "curl", "-s", url,
                "-X", "POST",
                "-H", "Content-Type: text/plain; charset=UTF-8",
                "-H", "Referer: https://pamyat-naroda.ru/heroes/",
                "-d", f"@{tmp_path}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return {"hits": {"total": 0, "hits": []}}

        data = json.loads(result.stdout)
        return data
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"  [ERROR] ES search {index}/{doc_type}: {e}")
        return {"hits": {"total": 0, "hits": []}}
    finally:
        os.unlink(tmp_path)


def build_query(last_name: str, first_name: str | None = None, middle_name: str | None = None) -> dict:
    """Построение ES-запроса."""
    must = [{"match": {"last_name": last_name}}]
    if first_name:
        must.append({"match": {"first_name": first_name}})
    if middle_name:
        must.append({"match": {"middle_name": middle_name}})
    return {"bool": {"must": must}}


def build_fuzzy_query(last_name: str, first_name: str | None = None) -> dict:
    """Fuzzy-запрос (поиск с ошибками в фамилии)."""
    must: list[dict[str, Any]] = [
        {"fuzzy": {"last_name": {"value": last_name, "fuzziness": 2}}}
    ]
    if first_name:
        must.append({"match": {"first_name": first_name}})
    return {"bool": {"must": must}}


def make_person_url(person_id: int | str) -> str:
    """Ссылка на страницу персоны."""
    return f"https://pamyat-naroda.ru/heroes/sm-person_guk{person_id}/"


def make_award_url(record_id: int | str) -> str:
    """Ссылка на наградной документ."""
    return f"https://pamyat-naroda.ru/heroes/podvig-chelovek_nagrazhdenie{record_id}/"


def classify_record(record: dict, known: dict) -> str:
    """Вердикт: НАШ / ВОЗМОЖНО / НЕ НАШ."""
    src = record.get("_source", {})
    score = 0
    contradictions = 0

    # Проверка года рождения
    date_birth = src.get("date_birth", "")
    if known.get("birth_year") and date_birth:
        try:
            year_str = date_birth.split(".")[-1]
            if year_str.isdigit():
                diff = abs(int(year_str) - known["birth_year"])
                if diff <= 3:
                    score += 1
                elif diff > 5:
                    contradictions += 1
        except (ValueError, IndexError):
            pass

    # Проверка отчества
    if known.get("middle_name") and src.get("middle_name"):
        if known["middle_name"].lower() == src["middle_name"].lower():
            score += 2  # Отчество — сильный сигнал
        elif known["middle_name"][:3].lower() != src["middle_name"][:3].lower():
            contradictions += 1

    # Проверка звания (если известно)
    if known.get("rank") and src.get("rank"):
        if known["rank"].lower() in src["rank"].lower() or src["rank"].lower() in known["rank"].lower():
            score += 1

    if contradictions > 0:
        return "НЕ НАШ"
    elif score >= 2:
        return "НАШ"
    elif score >= 1:
        return "ВОЗМОЖНО"
    else:
        return "ВОЗМОЖНО"  # Недостаточно данных для НЕ НАШ


def format_award_record(src: dict) -> dict:
    """Форматирование записи из nagrada_kartoteka."""
    return {
        "name": f"{src.get('last_name', '')} {src.get('first_name', '')} {src.get('middle_name', '')}".strip(),
        "birth_date": src.get("date_birth", "не указана"),
        "rank": src.get("rank", "не указано"),
        "award": src.get("naimenovanie_nagradi", "не указана"),
        "date": src.get("data_dokumenta", ""),
        "awarded_by": src.get("kto_nagradil", ""),
        "delivered": src.get("priznak_vrucheniya", ""),
        "archive": src.get("arhiv", ""),
        "person_id": src.get("person_id"),
        "record_id": src.get("id"),
        "person_url": make_person_url(src["person_id"]) if src.get("person_id") else None,
        "award_url": make_award_url(src["id"]) if src.get("id") else None,
    }


def format_loss_record(src: dict) -> dict:
    """Форматирование записи из memorial."""
    return {
        "name": f"{src.get('last_name', '')} {src.get('first_name', '')} {src.get('middle_name', '')}".strip(),
        "birth_date": src.get("date_birth", "не указана"),
        "rank": src.get("rank", "не указано"),
        "cause": src.get("prichina_vibitiya", ""),
        "date_loss": src.get("data_vibitiya", ""),
        "place_loss": src.get("mesto_vibitiya", ""),
        "burial": src.get("data_i_pervichnoe_mesto_zahoroneniya", ""),
        "unit": src.get("poslednee_mesto_sluzhbi", ""),
        "person_id": src.get("person_id"),
        "person_url": make_person_url(src["person_id"]) if src.get("person_id") else None,
    }


def run_search(
    last_name: str,
    first_name: str | None = None,
    middle_name: str | None = None,
    birth_year: int | None = None,
) -> dict:
    """Полный поиск по всем индексам ES API."""

    known = {
        "last_name": last_name,
        "first_name": first_name,
        "middle_name": middle_name,
        "birth_year": birth_year,
    }

    results: dict[str, Any] = {
        "query": known,
        "awards": [],
        "losses": [],
        "foreign_awards": [],
        "total_awards": 0,
        "total_losses": 0,
        "total_foreign": 0,
        "unique_persons": set(),
    }

    # === 1. Наградные карточки (основной индекс) ===
    # Ищем БЕЗ отчества (match по отчеству слишком строгий в ES)
    # Фильтрация по отчеству — в classify_record
    print(f"\n[1/4] Наградные карточки (nagrada_kartoteka)...")
    query = build_query(last_name, first_name)
    data = es_search("podvig", "nagrada_kartoteka", query)
    total = data.get("hits", {}).get("total", 0)
    hits = data.get("hits", {}).get("hits", [])
    results["total_awards"] = total
    print(f"  Найдено: {total} записей")

    for hit in hits:
        src = hit.get("_source", {})
        record = format_award_record(src)
        record["verdict"] = classify_record(hit, known)
        results["awards"].append(record)
        if src.get("person_id"):
            results["unique_persons"].add(src["person_id"])

    # === 2. Иностранные награды ===
    print(f"\n[2/4] Иностранные награды (nagrada_in_kartoteka)...")
    query_in = build_query(last_name, first_name)
    data = es_search("podvig", "nagrada_in_kartoteka", query_in)
    total = data.get("hits", {}).get("total", 0)
    hits = data.get("hits", {}).get("hits", [])
    results["total_foreign"] = total
    print(f"  Найдено: {total} записей")

    for hit in hits:
        src = hit.get("_source", {})
        record = format_award_record(src)
        record["verdict"] = classify_record(hit, known)
        results["foreign_awards"].append(record)

    # === 3. Донесения о потерях ===
    print(f"\n[3/4] Донесения о потерях (memorial)...")
    query_losses = build_query(last_name, first_name)
    data = es_search("memorial", "chelovek_donesenie", query_losses)
    total = data.get("hits", {}).get("total", 0)
    hits = data.get("hits", {}).get("hits", [])
    results["total_losses"] = total
    print(f"  Найдено: {total} записей")

    for hit in hits:
        src = hit.get("_source", {})
        record = format_loss_record(src)
        record["verdict"] = classify_record(hit, known)
        results["losses"].append(record)

    # === 4. Fuzzy поиск (если мало результатов) ===
    if results["total_awards"] < 3 and first_name:
        print(f"\n[4/4] Fuzzy поиск (вариации фамилии)...")
        fuzzy_query = build_fuzzy_query(last_name, first_name)
        data = es_search("podvig", "nagrada_kartoteka", fuzzy_query, size=10)
        fuzzy_total = data.get("hits", {}).get("total", 0)
        fuzzy_hits = data.get("hits", {}).get("hits", [])
        new_found = 0
        for hit in fuzzy_hits:
            src = hit.get("_source", {})
            pid = src.get("person_id")
            if pid and pid not in results["unique_persons"]:
                record = format_award_record(src)
                record["verdict"] = classify_record(hit, known)
                record["source"] = "fuzzy"
                results["awards"].append(record)
                results["unique_persons"].add(pid)
                new_found += 1
        print(f"  Дополнительно найдено: {new_found} (всего fuzzy: {fuzzy_total})")
    else:
        print(f"\n[4/4] Fuzzy поиск — пропущен (достаточно результатов)")

    # Убираем set (не сериализуемый)
    results["unique_persons"] = list(results["unique_persons"])

    return results


def print_report(results: dict) -> None:
    """Печать отчёта в консоль."""
    q = results["query"]
    name_parts = [q["last_name"]]
    if q["first_name"]:
        name_parts.append(q["first_name"])
    if q["middle_name"]:
        name_parts.append(q["middle_name"])
    full_name = " ".join(name_parts)

    print("\n" + "=" * 60)
    print(f"  ОТЧЁТ: {full_name}")
    if q["birth_year"]:
        print(f"  Год рождения: ~{q['birth_year']}")
    print("=" * 60)

    # Статистика
    total = results["total_awards"] + results["total_losses"] + results["total_foreign"]
    print(f"\n  Всего найдено: {total} записей")
    print(f"  - Награды: {results['total_awards']}")
    print(f"  - Иностранные награды: {results['total_foreign']}")
    print(f"  - Потери: {results['total_losses']}")
    print(f"  - Уникальных персон: {len(results['unique_persons'])}")

    # Награды
    if results["awards"]:
        print(f"\n--- НАГРАДЫ ({len(results['awards'])} записей) ---")
        for i, r in enumerate(results["awards"], 1):
            v_marker = {"НАШ": "+", "ВОЗМОЖНО": "?", "НЕ НАШ": "-"}.get(r["verdict"], "?")
            print(f"\n  [{v_marker}] {i}. {r['name']} ({r['birth_date']})")
            print(f"      Звание: {r['rank']}")
            print(f"      Награда: {r['award']} ({r['date']})")
            if r.get("awarded_by"):
                print(f"      Кто наградил: {r['awarded_by']}")
            print(f"      Вердикт: {r['verdict']}")
            if r.get("person_url"):
                print(f"      Ссылка: {r['person_url']}")

    # Потери
    if results["losses"]:
        print(f"\n--- ПОТЕРИ ({len(results['losses'])} записей) ---")
        for i, r in enumerate(results["losses"], 1):
            print(f"\n  {i}. {r['name']} ({r['birth_date']})")
            print(f"      Звание: {r['rank']}, Часть: {r.get('unit', '?')}")
            print(f"      Причина: {r.get('cause', '?')}, Дата: {r.get('date_loss', '?')}")
            print(f"      Место: {r.get('place_loss', '?')}")
            if r.get("burial"):
                print(f"      Захоронение: {r['burial']}")

    # Вывод
    our_count = sum(1 for r in results["awards"] if r["verdict"] == "НАШ")
    maybe_count = sum(1 for r in results["awards"] if r["verdict"] == "ВОЗМОЖНО")
    print(f"\n--- ИТОГ ---")
    print(f"  НАШ: {our_count} записей")
    print(f"  ВОЗМОЖНО: {maybe_count} записей")
    print(f"  В потерях: {'ДА' if results['losses'] else 'НЕТ (вероятно выжил)'}")


def save_json(results: dict, output_dir: str = "data") -> str:
    """Сохранение результатов в JSON."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    q = results["query"]
    filename = f"{q['last_name']}_{q.get('first_name', 'X')}".lower()
    filepath = os.path.join(output_dir, f"{filename}_results.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Результат сохранён: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Память 9 Мая — Research Pipeline")
    parser.add_argument("--last-name", required=True, help="Фамилия")
    parser.add_argument("--first-name", help="Имя")
    parser.add_argument("--middle-name", help="Отчество")
    parser.add_argument("--birth-year", type=int, help="Год рождения (приблизительный)")
    parser.add_argument("--output", default="data", help="Папка для результатов")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  ПАМЯТЬ 9 МАЯ — Research Pipeline")
    print(f"  Поиск: {args.last_name} {args.first_name or ''} {args.middle_name or ''}")
    print(f"{'='*60}")

    results = run_search(
        last_name=args.last_name,
        first_name=args.first_name,
        middle_name=args.middle_name,
        birth_year=args.birth_year,
    )

    print_report(results)
    save_json(results, args.output)


if __name__ == "__main__":
    main()
