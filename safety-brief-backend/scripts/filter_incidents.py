"""職場のあんぜんサイト 労働災害（死傷）データベースから、
「製造業」かつ「試験・実験・開発・測定」に関連する事例を抽出するスクリプト。

このスクリプトは、厚生労働省のサイト (anzeninfo.mhlw.go.jp) からブラウザで
ダウンロードした CSV / Excel ファイルを入力にとる。ネットワークアクセスは
行わない（ダウンロードはあらかじめ手動で行っておくこと）。

実行方法（このPCで、pandas / openpyxl をインストールした上で）:
    pip install pandas openpyxl
    python filter_incidents.py data/*.xlsx

出力: manufacturing_test_incidents.csv （抽出された事例の一覧）
"""

import glob
import sys

import pandas as pd

# 職場のあんぜんサイトの労働災害（死傷）データベースの列順（22列固定）
COLUMNS = [
    "id",
    "era",
    "year_in_era",
    "month",
    "time_range",
    "description",
    "industry_major_code",
    "industry_major_name",
    "industry_middle_code",
    "industry_middle_name",
    "industry_minor_code",
    "industry_minor_name",
    "workplace_size",
    "cause_major_code",
    "cause_major_name",
    "cause_middle_code",
    "cause_middle_name",
    "cause_minor_code",
    "cause_minor_name",
    "accident_type_code",
    "accident_type_name",
    "age",
]

TARGET_INDUSTRY = "製造業"
KEYWORDS = ["試験", "実験", "開発", "測定"]


def load_file(path):
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path, skiprows=2, header=None, encoding="utf-8", dtype=str)
    else:
        df = pd.read_excel(path, skiprows=2, header=None, dtype=str)
    df.columns = COLUMNS[: len(df.columns)]
    return df


def main(paths):
    if not paths:
        print("使い方: python filter_incidents.py <ファイルパスまたはglobパターン> ...")
        return

    expanded_paths = []
    for p in paths:
        matched = glob.glob(p)
        expanded_paths.extend(matched if matched else [p])

    frames = []
    for path in expanded_paths:
        try:
            frames.append(load_file(path))
            print(f"読み込み成功: {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"スキップ: {path} ({exc})")

    if not frames:
        print("読み込めるファイルがありませんでした。")
        return

    all_df = pd.concat(frames, ignore_index=True)

    manufacturing = all_df[all_df["industry_major_name"] == TARGET_INDUSTRY]
    pattern = "|".join(KEYWORDS)
    matched = manufacturing[manufacturing["description"].str.contains(pattern, na=False)]

    print(f"\n読み込んだ全件数: {len(all_df)}")
    print(f"製造業: {len(manufacturing)}件")
    print(f"うちキーワード（{'/'.join(KEYWORDS)}）一致: {len(matched)}件")

    output_path = "manufacturing_test_incidents.csv"
    matched.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"-> {output_path} に出力しました")


if __name__ == "__main__":
    main(sys.argv[1:])
