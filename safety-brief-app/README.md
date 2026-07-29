# safety-brief-app

`safety-brief-backend` の動作確認用の最小限の Expo (React Native) アプリです。
作業内容をテキストで入力して `POST /safety-brief` を叩き、レスポンス
（安全ブリーフィングと類似災害事例）を画面に表示します。

Claudeの回答は `expo-speech`（端末内蔵の音声合成、Google Cloud TTSではありません）で
読み上げ可能です。音声入力（マイク→テキスト化）のコードは準備済みですが、
**実機でのビルド・動作確認はまだ行っていません**（下記「音声入力（マイク）」参照）。

## セットアップ

`safety-brief-backend` を起動した PC（Precision 5820 など）と同じ
Wi-Fi にスマホを接続したうえで:

```bash
cd safety-brief-app
npm install
npx expo start
```

表示された QR コードをスマホの **Expo Go** アプリで読み取ってください。

## 使い方

1. 「バックエンドURL」欄に、バックエンドを起動しているPCのローカルIPを入力
   （例: `http://192.168.0.163:8000`）。コードのデフォルト値は開発時に
   使用したIPなので、環境が変わったら書き換えてください。
2. 「作業内容」に作業内容を入力（例: `足場の組立で高さ5mの作業`）
3. 「施設種別」は任意
4. 「安全ブリーフィングを取得」をタップ
5. Claude が生成した安全ブリーフィングと、類似の過去災害事例が表示されます
6. 「🔊 音声で聴く」をタップすると、安全ブリーフィングを端末の音声合成で
   読み上げます（もう一度タップ、または「⏹ 停止」で停止）

## オフラインモード（サーバー・インターネット不要）

画面上部の「オフラインモード」をONにすると、バックエンドに一切接続せず、
アプリに同梱した実際の労働災害事例84件（`data/incidents.json`、厚生労働省
「職場のあんぜんサイト」由来）から、文字bi-gramベースの簡易類似度検索
（`lib/offlineSearch.js`）で類似事例を探し、その場に登録済みの再発防止策
(`preventive`)をそのまま表示します。

トレードオフとして、Claudeによるその場での動的な生成ではなく、
過去事例に紐づく固定文の再発防止策になります。また埋め込みモデルのような
高精度な意味的検索ではなく、文字の重なりに基づく簡易検索です（Sentence
Transformersのような埋め込みモデルはスマホ単体では重すぎて非現実的なため）。
Expo Goでは動かせないネイティブ音声認識と違い、この機能はJavaScriptのみで
完結するため、そのままExpo Goで動作します。

`data/incidents.json` を更新する場合は、`safety-brief-backend/data/incident_db.json`
をコピーしてください。

## 音声入力（マイク） -- 準備済み・未ビルド

`expo-speech-recognition`（Expo SDK 54対応版、`sdk-54` distタグ = 3.1.3）を
組み込み済みです。「作業内容」欄の横に🎤ボタンがありますが、**Expo Goでは
使用できないため、意図的に無効化（グレーアウト）されています**
（`app.json`の設定プラグインがネイティブコードを追加するため、カスタム開発
ビルドが必須。詳細はライブラリのREADMEの「Installation」参照）。

次回、実機でマイク入力を試すための手順:

1. [Expoアカウント](https://expo.dev/)を作成し、ログイン
   ```bash
   npx eas-cli login
   ```
2. プロジェクトをEASに登録（初回のみ）
   ```bash
   npx eas-cli build:configure
   ```
3. 開発ビルドを作成（Androidの場合。クラウドビルドのため10〜20分程度かかります）
   ```bash
   npx eas-cli build --profile development --platform android
   ```
4. ビルド完了後に案内されるURL/QRコードから、生成されたAPK
   （**Expo Goとは別の専用アプリ**）をスマホにインストール
5. 開発サーバーを起動し、インストールしたアプリから接続
   ```bash
   npx expo start --dev-client
   ```
6. 🎤ボタンが有効になっているはずなので、タップして動作確認
   （マイク・音声認識の権限許可が求められます）

`eas.json` に `development` / `preview` / `production` の3プロファイルを
用意済みです。

## 注意

- バックエンド側の Windows ファイアウォールでポート8000への
  インバウンド接続を許可しておく必要があります
- HTTP（非暗号化）通信のため、開発用ネットワーク以外では使用しないでください
- Expo SDK は意図的に **54** に固定しています。Play Store / App Store の
  Expo Go アプリが対応しているのが SDK 54 までのため（2026年半ば時点、
  新しいSDKは審査待ち）。`npx expo install --fix` 等で最新版に上げると
  「Project is incompatible with this version of Expo Go」エラーが再発します
