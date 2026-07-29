"""filter_incidents.py の出力（例: manufacturing_test_incidents.csv）を、
safety-brief-backend の INCIDENT_DB 用 JSON データに変換するスクリプト。

各事例について:
- date: 年号+年+月から生成（日は元データに無いため月単位 "YYYY-MM"）
- facility: 業種（中分類）を使用
- work_type: 起因物（小分類、なければ中分類）を使用
- description: 災害状況をそのまま使用
- severity: 固定で "injury"（このデータベースは休業4日以上の事例のみのため）
- preventive: Claude に、事故の型・起因物・災害状況から簡潔な再発防止策を
  生成させる（生成に失敗した事例のみ、汎用的な文言で代用）

実行方法（safety-brief-backend の venv で。anthropic は既にインストール済み）:
    python build_incident_db.py manufacturing_test_incidents.csv

出力: incident_db.json
  -> safety-brief-backend/data/incident_db.json に配置すると、
     main.py がダミーDBの代わりにこちらを読み込む。
"""

import csv
import json
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

BATCH_SIZE = 20
GENERIC_PREVENTIVE = "作業手順・保護具の確認を徹底し、同種災害の再発を防止する"

ERA_BASE_YEAR = {"令和": 2018, "平成": 1988, "昭和": 1925}


def to_date(row):
    base = ERA_BASE_YEAR.get(row.get("era", "").strip())
    if base is None:
        return ""
    try:
        year = base + int(row["year_in_era"])
        month = int(row["month"])
    except (ValueError, KeyError):
        return ""
    return f"{year:04d}-{month:02d}"


def to_facility(row):
    return row.get("industry_middle_name") or row.get("industry_major_name") or ""


def to_work_type(row):
    minor = row.get("cause_minor_name", "")
    middle = row.get("cause_middle_name", "")
    if minor and minor not in ("その他", "その他の起因物"):
        return minor
    return middle or minor


def build_prompt(batch):
    lines = [
        f"{row['id']}: 事故の型={row.get('accident_type_name', '')} / "
        f"起因物={to_work_type(row)} / 状況={row['description']}"
        for row in batch
    ]
    joined = "\n".join(lines)
    return (
        "以下は実際の労働災害事例です。それぞれについて、同種の災害を防ぐための"
        "再発防止策を、実務的で簡潔な一文（30〜60字程度）で日本語で作成してください。\n\n"
        f"{joined}\n\n"
        "出力形式（他の説明文は一切書かないこと。1行に1件、`ID:再発防止策の文章`の形式）:\n"
        "例:\n1:可動部にカバーを設置し、稼働中の手指の接近を禁止する\n"
    )


def generate_preventive_batch(client, batch):
    prompt = build_prompt(batch)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(block.text for block in response.content if block.type == "text")

    result = {}
    for line in text.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        id_part, preventive = line.split(":", 1)
        id_part = id_part.strip()
        if id_part.isdigit():
            result[id_part] = preventive.strip()
    return result


def main(input_path):
    if not CLAUDE_API_KEY:
        print("CLAUDE_API_KEY が設定されていません（.env を確認してください）")
        return

    with open(input_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    preventive_map = {}
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        print(f"再発防止策を生成中: {i + 1}〜{i + len(batch)} / {len(rows)}件")
        preventive_map.update(generate_preventive_batch(client, batch))

    incidents = []
    missing_preventive = 0
    for row in rows:
        preventive = preventive_map.get(row["id"])
        if not preventive:
            missing_preventive += 1
            preventive = GENERIC_PREVENTIVE
        incidents.append(
            {
                "date": to_date(row),
                "facility": to_facility(row),
                "work_type": to_work_type(row),
                "description": row["description"],
                "severity": "injury",
                "preventive": preventive,
            }
        )

    if missing_preventive:
        print(f"再発防止策の生成に失敗: {missing_preventive}件（汎用文で代用）")

    output_path = "incident_db.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(incidents, f, ensure_ascii=False, indent=2)

    print(f"-> {output_path} に {len(incidents)}件を出力しました")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使い方: python build_incident_db.py <入力CSVファイル>")
        sys.exit(1)
    main(sys.argv[1])
