# safety-brief-backend

労働災害防止音声会話アプリ - FastAPI バックエンド（Phase 1）

作業前にスマホマイクで話した「これから行う作業」の説明を受け取り、
類似する過去の労働災害事例を検索したうえで、Claude に安全ブリーフィングを
生成させて返す REST API です。

## 現在の実装範囲

- FastAPI による REST API（`/health`, `/safety-brief`, `/safety-chat`）
- 災害DBに対する類似度検索
  - `data/incident_db.json` があればそれを読み込み（`scripts/` の
    データ抽出・変換スクリプトで、厚生労働省「職場のあんぜんサイト」の
    労働災害（死傷）データベースから実データを生成可能。詳細は
    `scripts/filter_incidents.py` / `scripts/classify_incidents.py` /
    `scripts/build_incident_db.py` を参照）
  - 無ければダミーDB（Python list、6件）にフォールバック
  - Sentence Transformers（`paraphrase-multilingual-MiniLM-L12-v2`）で埋め込み
  - モデルが読み込めない環境（オフライン等）では自動的にキーワード類似度に
    フォールバック
- Claude API（Messages API）による安全ブリーフィング生成
  - タイムアウト（デフォルト25秒、`CLAUDE_TIMEOUT_SECONDS`で変更可）時はフォールバック文言を **504** で返却
  - `CLAUDE_API_KEY` 未設定時もフォールバック文言を返却（開発用）
- CORS 有効化（スマホの Expo Go クライアントからの接続を想定）
- 認証なし（開発時のみ）

未実装（Phase 2以降）:

- Weaviate / Pinecone などの本格的なベクトルDB
- Google Cloud TTS による音声合成
- スマホとの実機通信テスト

## セットアップ

```bash
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
$ cp .env.example .env
# .env を編集して CLAUDE_API_KEY に実際のキーを設定する
```

## 起動

```bash
$ uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- API: http://0.0.0.0:8000
- OpenAPI ドキュメント: http://[Precision_5820_IP]:8000/docs

スマホの Expo Go からは `http://[PC_IP]:8000/safety-brief` に POST してください
（PCとスマホが同一 Wi-Fi 上にあることが必要です）。

## クラウドデプロイ（PCを起動しておく必要をなくす）

PC（Precision 5820）がオフラインでも常時使えるようにしたい場合、
リポジトリ直下の `render.yaml` を使って [Render](https://render.com) に
デプロイできます。

1. Render にサインアップし、GitHub リポジトリを連携
2. 「New Blueprint」からこのリポジトリを選択（`render.yaml` を自動検出）
3. `CLAUDE_API_KEY` を環境変数として入力（`sync: false` のためダッシュボードで設定が必要）
4. デプロイ完了後に発行される `https://xxxx.onrender.com` を、
   Expo アプリの「バックエンドURL」欄に入力する

**注意点:**

- クラウド版は `requirements-cloud.txt` を使用し、`sentence-transformers` /
  `torch` を含めていません（無料プランのメモリに収まらないため）。
  埋め込みモデルが無い場合は自動でキーワード類似度検索にフォールバックする
  設計なので、コード変更なしでそのまま動作します（精度はローカル版より
  やや落ちます）
- Render の無料プランは一定時間アクセスがないとスリープするため、
  スリープ復帰後の初回リクエストは数十秒かかることがあります
- HTTPS になるため、Expo アプリ側は `http://` ではなく `https://` の
  URLを入力してください

## 環境変数（.env）

| 変数名 | 説明 | デフォルト |
| --- | --- | --- |
| `CLAUDE_API_KEY` | Claude API キー | なし（未設定時はフォールバック応答） |
| `LOG_LEVEL` | ログレベル（DEBUG/INFO/...） | `INFO` |
| `API_PORT` | uvicorn 起動時のポート | `8000` |
| `API_HOST` | uvicorn 起動時のホスト | `0.0.0.0` |
| `CLAUDE_MODEL` | 使用する Claude モデル ID | `claude-sonnet-5` |
| `SENTENCE_MODEL_NAME` | 埋め込みに使う Sentence Transformers モデル | `paraphrase-multilingual-MiniLM-L12-v2` |
| `CLAUDE_TIMEOUT_SECONDS` | Claude API呼び出しのタイムアウト秒数 | `25.0` |
| `COMPANY_INCIDENT_TAGS` | 検索結果の上位に優先表示する社内事例の目印（`industry_minor_name`列の値、カンマ区切りで複数可） | `トヨタ` |

## API

### GET /health

サーバー起動確認用。

```json
{"status": "ok"}
```

### POST /safety-brief

リクエスト:

```json
{
  "work_description": "足場の組立で高さ5mの作業",
  "facility_type": "建設現場"
}
```

レスポンス（200）:

```json
{
  "text": "この作業の危険性は落下リスクです。以下が重要な安全ポイント...",
  "incident_count": 5,
  "incidents": [
    {
      "date": "2023-12-15",
      "description": "手すり未設置で転落",
      "severity": "fatal"
    }
  ],
  "prompt": "【過去の類似災害事例】\n...【これからの作業】\n..."
}
```

`prompt` は Claude に実際に送った最初のメッセージ（類似事例＋作業内容）。
`/safety-chat` で追加質問する際、会話履歴の1件目としてそのまま使う。

エラー:

- `work_description` が空文字 → `400 Bad Request`
- Claude API がタイムアウト（デフォルト25秒） → `504`（フォールバック本文つき）

### POST /safety-chat

`/safety-brief` の結果に対する追加質問に答える。サーバー側はセッションを
持たないステートレス設計で、クライアントが会話履歴を保持して毎回送り返す。

リクエスト:

```json
{
  "history": [
    {"role": "user", "content": "（/safety-briefのpromptをそのまま）"},
    {"role": "assistant", "content": "（/safety-briefのtextをそのまま）"}
  ],
  "message": "保護具は何が必要ですか？"
}
```

レスポンス（200）:

```json
{
  "reply": "フルハーネス型安全帯と保護メガネが必要です。",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "保護具は何が必要ですか？"},
    {"role": "assistant", "content": "フルハーネス型安全帯と保護メガネが必要です。"}
  ]
}
```

返ってきた `history` をそのまま次回の `history` として送り返せば、会話が続く。

エラー:

- `message` が空文字 → `400 Bad Request`

## 社内の災害事例を追加する

国の実データと同じ仕組みで追加できる。

1. `safety-brief-backend/manufacturing_test_incidents.csv` を開き、
   `filter_incidents.py` が出力する22列の形式（詳細は
   `scripts/filter_incidents.py` のヘッダー定義を参照）で新しい行を追加する
2. `industry_minor_name` 列に社名（例: `トヨタ`）を入力する。この値が
   `COMPANY_INCIDENT_TAGS`（デフォルト`トヨタ`）と一致する事例は、
   検索結果の上位に優先表示される
3. 再変換する
   ```bash
   cd scripts
   python build_incident_db.py ../manufacturing_test_incidents.csv
   mv incident_db.json ../data/incident_db.json
   ```
4. コミット・プッシュしてデプロイ先（Render）に反映する

Renderはデプロイのたびにファイルシステムがリセットされるため、事例の追加は
「ファイル編集→git push→再デプロイ」のサイクルが必要（アプリからその場で
追加することはできない）。

## 動作確認

サーバー起動後、別ターミナルで:

```bash
$ python test_api.py
```

`GET /health`、`POST /safety-brief`（正常系・異常系）を実行し、結果を表示します。

curl での確認例:

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/safety-brief \
  -H "Content-Type: application/json" \
  -d '{"work_description": "足場の組立で高さ5mの作業"}'
```

同一 LAN 内の別端末からは `127.0.0.1` の代わりに Precision 5820 の
ローカル IP（例: `192.168.x.x`）を使用してください。
