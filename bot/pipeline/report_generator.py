#!/usr/bin/env python3
"""
Report Generator — генерация HTML-отчёта из результатов pipeline.

Использование:
    python3 pipeline/report_generator.py data/бурмистров_прокофий_results.json
    python3 pipeline/report_generator.py data/бурмистров_прокофий_results.json --output reports/
"""

import json
import argparse
import os
from pathlib import Path
from datetime import datetime


def generate_html(results: dict) -> str:
    """Генерация HTML-отчёта в советском стиле."""
    q = results["query"]
    name_parts = [q["last_name"]]
    if q.get("first_name"):
        name_parts.append(q["first_name"])
    if q.get("middle_name"):
        name_parts.append(q["middle_name"])
    full_name = " ".join(name_parts)

    birth_year = q.get("birth_year", "")
    birth_str = f", {birth_year} г.р." if birth_year else ""

    # Фильтруем НАШ и ВОЗМОЖНО
    our_awards = [r for r in results.get("awards", []) if r["verdict"] == "НАШ"]
    maybe_awards = [r for r in results.get("awards", []) if r["verdict"] == "ВОЗМОЖНО"]
    losses = results.get("losses", [])

    total_found = results.get("total_awards", 0) + results.get("total_losses", 0)
    our_count = len(our_awards)

    # Определяем звание и часть из первой записи НАШ
    rank = our_awards[0]["rank"] if our_awards else (maybe_awards[0]["rank"] if maybe_awards else "не определено")
    unit = ""
    for r in our_awards:
        if r.get("awarded_by") and r["awarded_by"] not in ("Президиум ВС СССР",):
            unit = r["awarded_by"]
            break

    # Уникальные награды НАШ
    seen_awards: set[str] = set()
    unique_awards = []
    for r in our_awards:
        key = r["award"]
        if key not in seen_awards:
            seen_awards.add(key)
            unique_awards.append(r)

    today = datetime.now().strftime("%d.%m.%Y")

    # George ribbon CSS
    george_css = """
    .george-stripe {
        background: repeating-linear-gradient(180deg,
            #2D0505 0px, #2D0505 4px, #E87B2F 4px, #E87B2F 8px);
        width: 6px;
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
    }
    .george-stripe-h {
        background: repeating-linear-gradient(90deg,
            #2D0505 0px, #2D0505 4px, #E87B2F 4px, #E87B2F 8px);
        height: 6px;
        width: 100%;
    }
    """

    awards_html = ""
    for i, r in enumerate(unique_awards, 1):
        awards_html += f"""
        <div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #EBDBC0;">
            <span style="width:8px;height:8px;border-radius:50%;background:#DAA520;flex-shrink:0;"></span>
            <span style="flex:1;font-size:14px;color:#2A2520;">{r['award']}</span>
            <span style="font-size:12px;color:#8A8278;font-family:'Courier New',monospace;">{r['date']}</span>
        </div>"""

    losses_html = ""
    if losses:
        for r in losses:
            losses_html += f"""
        <div style="padding:8px 0;border-bottom:1px solid #EBDBC0;">
            <div style="font-size:14px;color:#2A2520;"><strong>{r['name']}</strong></div>
            <div style="font-size:12px;color:#6B6358;">Причина: {r.get('cause', '?')} | Дата: {r.get('date_loss', '?')}</div>
            <div style="font-size:12px;color:#6B6358;">Место: {r.get('place_loss', '?')}</div>
            {f'<div style="font-size:12px;color:#6B6358;">Захоронение: {r["burial"]}</div>' if r.get("burial") else ""}
        </div>"""

    maybe_html = ""
    if maybe_awards[:3]:
        for r in maybe_awards[:3]:
            maybe_html += f"""
        <div style="padding:6px 0;border-bottom:1px solid #EBDBC0;opacity:0.7;">
            <div style="font-size:13px;color:#6B6358;">{r['name']} ({r['birth_date']}) — {r['rank']}</div>
            <div style="font-size:12px;color:#8A8278;">{r['award']} ({r['date']})</div>
        </div>"""

    person_url = our_awards[0].get("person_url", "") if our_awards else ""
    person_link = f'<a href="{person_url}" style="color:#CC1133;text-decoration:underline;font-size:13px;">Открыть на Памяти народа</a>' if person_url else ""

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Боевой путь — {full_name}</title>
<link href="https://fonts.googleapis.com/css2?family=PT+Serif:wght@400;700&family=PT+Sans:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: 'PT Serif', Georgia, serif;
    background: #F5E6D3;
    color: #2A2520;
    padding: 20px;
    max-width: 700px;
    margin: 0 auto;
  }}
  {george_css}
  .report-card {{
    background: #FAF3E8;
    border: 1px solid #C4A97A;
    border-radius: 4px;
    padding: 24px 24px 24px 32px;
    position: relative;
    box-shadow: 2px 2px 8px rgba(92,74,48,0.15), inset 0 0 40px rgba(160,128,80,0.05);
    margin-bottom: 16px;
  }}
  .section-title {{
    font-family: 'PT Sans', sans-serif;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .star {{ color: #CC1133; }}
  .gold {{ color: #DAA520; }}
  .stamp {{
    position: absolute;
    top: 16px;
    right: 16px;
    color: rgba(178,34,34,0.15);
    font-size: 12px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    border: 2px solid rgba(178,34,34,0.12);
    border-radius: 50%;
    padding: 6px 12px;
    transform: rotate(-12deg);
    font-family: 'PT Sans', sans-serif;
  }}
  .divider {{
    height: 1px;
    background: linear-gradient(90deg, transparent, #C4A97A, transparent);
    margin: 16px 0;
  }}
  .footer-text {{
    font-family: 'PT Sans', sans-serif;
    font-size: 11px;
    color: #8A8278;
    text-align: center;
    margin-top: 16px;
  }}
</style>
</head>
<body>

<!-- Header -->
<div style="text-align:center;margin-bottom:20px;">
  <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:8px;">
    <span style="color:#CC1133;font-size:20px;">&#9733;</span>
    <span style="font-family:'Courier New',monospace;font-size:12px;color:#DAA520;letter-spacing:0.25em;font-weight:700;">1941 — 1945</span>
    <span style="color:#CC1133;font-size:20px;">&#9733;</span>
  </div>
  <h1 style="font-size:24px;font-weight:700;margin-bottom:4px;">{full_name}</h1>
  <p style="font-size:14px;color:#6B6358;font-family:'PT Sans',sans-serif;">{rank}{f' | {unit}' if unit else ''}{birth_str}</p>
</div>

<div class="george-stripe-h" style="margin-bottom:20px;"></div>

<!-- Stats -->
<div style="display:flex;gap:12px;margin-bottom:20px;font-family:'PT Sans',sans-serif;">
  <div style="flex:1;text-align:center;background:#FAF3E8;border:1px solid #C4A97A;border-radius:4px;padding:12px;">
    <div style="font-size:24px;font-weight:700;color:#CC1133;">{our_count}</div>
    <div style="font-size:11px;color:#6B6358;">подтверждённых наград</div>
  </div>
  <div style="flex:1;text-align:center;background:#FAF3E8;border:1px solid #C4A97A;border-radius:4px;padding:12px;">
    <div style="font-size:24px;font-weight:700;color:#CC1133;">{total_found}</div>
    <div style="font-size:11px;color:#6B6358;">записей в архивах</div>
  </div>
  <div style="flex:1;text-align:center;background:#FAF3E8;border:1px solid #C4A97A;border-radius:4px;padding:12px;">
    <div style="font-size:24px;font-weight:700;color:{'#CC1133' if losses else '#4A7C4E'};">{'ПОГИБ' if losses else 'ВЫЖИЛ'}</div>
    <div style="font-size:11px;color:#6B6358;">статус</div>
  </div>
</div>

<!-- Awards -->
<div class="report-card">
  <div class="george-stripe"></div>
  <div class="stamp">ЦАМО</div>
  <div class="section-title gold">&#9733; Награды ({len(unique_awards)})</div>
  {awards_html}
  <div style="margin-top:8px;">{person_link}</div>
</div>

{'<!-- Losses -->' + chr(10) + '<div class="report-card"><div class="george-stripe"></div><div class="section-title star">&#9733; Сведения о потерях</div>' + losses_html + '</div>' if losses else '<!-- No losses — survived -->'}

{f'''<!-- Maybe -->
<div class="report-card" style="opacity:0.7;">
  <div class="george-stripe"></div>
  <div class="section-title" style="color:#8A8278;">Возможные совпадения ({len(maybe_awards)})</div>
  <p style="font-size:12px;color:#8A8278;margin-bottom:8px;font-family:'PT Sans',sans-serif;">Записи, которые могут относиться к другим людям с похожим ФИО</p>
  {maybe_html}
</div>''' if maybe_awards else ''}

<!-- Sources -->
<div class="report-card">
  <div class="george-stripe"></div>
  <div class="section-title" style="color:#6B6358;">Источники</div>
  <p style="font-size:12px;color:#6B6358;font-family:'PT Sans',sans-serif;line-height:1.6;">
    Данные получены из открытых государственных архивов:<br>
    Память народа (pamyat-naroda.ru) &bull; Подвиг народа (podvignaroda.ru) &bull; ОБД Мемориал (obd-memorial.ru)<br>
    Архив: ЦАМО (Центральный архив Министерства обороны РФ)
  </p>
</div>

<!-- Disclaimer -->
<div class="divider"></div>
<div class="footer-text">
  <p>Отчёт подготовлен сервисом "Память 9 Мая" &bull; {today}</p>
  <p style="margin-top:4px;font-style:italic;color:#A08050;">Данный отчёт основан на открытых архивных данных и не является официальным документом.</p>
  <p style="margin-top:8px;color:#CC1133;">&#9733; Помним. Гордимся. &#9733;</p>
</div>

</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="Report Generator — HTML-отчёт из результатов pipeline")
    parser.add_argument("input", help="JSON-файл с результатами pipeline")
    parser.add_argument("--output", default="data/reports", help="Папка для отчётов")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        results = json.load(f)

    html = generate_html(results)

    Path(args.output).mkdir(parents=True, exist_ok=True)
    q = results["query"]
    filename = f"{q['last_name']}_{q.get('first_name', 'X')}_report.html".lower()
    filepath = os.path.join(args.output, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Отчёт создан: {filepath}")
    return filepath


if __name__ == "__main__":
    main()
