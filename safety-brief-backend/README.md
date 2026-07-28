# safety-brief-backend

労働災害防止音声会話アプリ - FastAPI バックエンド（Phase 1）

作業前にスマホマイクで話した「これから行う作業」の説明を受け取り、
類似する過去の労働災害事例を検索したうえで、Claude に安全ブリーフィングを
生成させて返す REST API です。

## 現在の実装範囲

- FastAPI による REST API（`/health`, `/safety-brief`）
- ダミー災害DB（Python list、6件）に対する類似度検索
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
  ]
}
```

エラー:

- `work_description` が空文字 → `400 Bad Request`
- Claude API がタイムアウト（デフォルト25秒） → `504`（フォールバック本文つき）

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
