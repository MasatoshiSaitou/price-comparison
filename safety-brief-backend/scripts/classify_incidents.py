"""filter_incidents.py の出力（manufacturing_test_incidents.csv）から、
実際に開発試験職場（研究開発・試験・実験・測定業務）に関連する事例だけを
Claude に判定させて絞り込むスクリプト。

「開発」「試験」等のキーワードが単に会社名・部署名に含まれるだけの事例や、
体温測定・在庫の計量など無関係な事例を除外する。

実行方法（safety-brief-backend の venv で。anthropic は既にインストール済み）:
    python classify_incidents.py manufacturing_test_incidents.csv

出力:
    manufacturing_incidents_filtered.csv （該当と判定された事例）
    manufacturing_incidents_excluded.csv （除外された事例）
"""

import csv
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

BATCH_SIZE = 30
RELEVANT_LABEL = "該当"
EXCLUDED_LABEL = "除外"


def build_prompt(batch):
    lines = "\n".join(f"{row['id']}: {row['description']}" for row in batch)
    return (
        "以下は労働災害データベースから「製造業」×「試験/実験/開発/測定」という"
        "キーワードで機械的に抽出した労働災害事例です。\n\n"
        "各事例について、実際に研究開発・試験・実験・測定業務の最中に発生した"
        f"災害であれば「{RELEVANT_LABEL}」、単に会社名や部署名に「開発」「試験」が"
        "含まれるだけ、あるいは体温測定・在庫の計量・単なる移動中の転倒など"
        f"業務内容そのものに無関係な事例であれば「{EXCLUDED_LABEL}」と判定してください。\n\n"
        f"{lines}\n\n"
        f"出力形式（他の説明文は一切書かないこと。1行に1件、`ID,{RELEVANT_LABEL}または{EXCLUDED_LABEL}` の形式）:\n"
        f"例:\n1,{RELEVANT_LABEL}\n2,{EXCLUDED_LABEL}\n"
    )


def classify_batch(client, batch):
    prompt = build_prompt(batch)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(block.text for block in response.content if block.type == "text")

    verdicts = {}
    for line in text.splitlines():
        line = line.strip()
        if "," not in line:
            continue
        id_part, verdict = line.split(",", 1)
        id_part = id_part.strip()
        verdict = verdict.strip()
        if id_part.isdigit():
            verdicts[id_part] = verdict
    return verdicts


def main(input_path):
    if not CLAUDE_API_KEY:
        print("CLAUDE_API_KEY が設定されていません（.env を確認してください）")
        return

    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    all_verdicts = {}
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        print(f"判定中: {i + 1}〜{i + len(batch)} / {len(rows)}件")
        all_verdicts.update(classify_batch(client, batch))

    relevant_rows = [r for r in rows if all_verdicts.get(r["id"]) == RELEVANT_LABEL]
    excluded_rows = [r for r in rows if all_verdicts.get(r["id"]) != RELEVANT_LABEL]
    unparsed = [r for r in rows if r["id"] not in all_verdicts]

    print(f"\n該当: {len(relevant_rows)}件")
    print(f"除外: {len(excluded_rows) - len(unparsed)}件")
    if unparsed:
        print(f"判定失敗（保守的に除外扱い、要確認）: {len(unparsed)}件")

    with open("manufacturing_incidents_filtered.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(relevant_rows)

    with open("manufacturing_incidents_excluded.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(excluded_rows)

    print(
        "-> manufacturing_incidents_filtered.csv（該当）/ "
        "manufacturing_incidents_excluded.csv（除外）に出力しました"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使い方: python classify_incidents.py <入力CSVファイル>")
        sys.exit(1)
    main(sys.argv[1])
