# safety-brief-app

`safety-brief-backend` の動作確認用の最小限の Expo (React Native) アプリです。
作業内容をテキストで入力して `POST /safety-brief` を叩き、レスポンス
（安全ブリーフィングと類似災害事例）を画面に表示します。

Claudeの回答は `expo-speech`（端末内蔵の音声合成、Google Cloud TTSではありません）で
読み上げ可能です。🎤ボタンをタップして話しかけると、音声認識でテキスト化され、
**話し終わると同時に自動で安全ブリーフィングを取得**します（ボタンの再タップ不要）。
ただし音声入力はExpo Goでは動作せず、カスタム開発ビルドが必須です
（下記「音声入力（マイク）」参照、実機で動作確認済み）。

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
7. オンラインモードのみ、結果の下に「追加で質問する」欄が表示されます。
   「保護具は何が必要ですか？」のように聞き返すと、最初のブリーフィングの
   文脈（類似事例＋作業内容）を踏まえてClaudeが回答します（バックエンドの
   `/safety-chat` を使用。会話履歴はアプリ側で保持し、毎回送り返す
   ステートレスな設計）

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

## 音声入力（マイク） -- 実機で動作確認済み

`expo-speech-recognition`（Expo SDK 54対応版、`sdk-54` distタグ = 3.1.3）と
`expo-dev-client`を組み込み済みです。「作業内容」欄の横の🎤ボタンをタップ
すると録音が始まり、話し終わる（無音を検知、または🎤を再タップ）と自動で
テキスト化され、そのまま自動で「安全ブリーフィングを取得」まで実行されます
（`App.js`の`submitBriefing`／音声認識の`end`イベントで実装）。

**Expo Goでは動作しません**（`app.json`の設定プラグインがネイティブコードを
追加するため、カスタム開発ビルドが必須）。ネイティブモジュールが無い環境
（Expo Go含む）では🎤ボタンは自動的にグレーアウトし、それ以外の機能
（テキスト入力・オンライン/オフラインモード・音声読み上げ）はExpo Goの
ままで問題なく動作します。

Androidの音声認識はデフォルトだと無音検知までの時間が短く、言語モデルも
短いフレーズ向けの挙動になりやすいため、単語単位で切れてしまうことが
ありました。`androidIntentOptions`（`EXTRA_LANGUAGE_MODEL: "web_search"`、
`EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS`等）で調整済みです。

カスタム開発ビルドの作り方:

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
   - Google Play プロテクトが「安全ではないアプリをブロックしました」と
     警告することがあります。ブロック画面の**「インストールする」という
     小さいテキストリンク**（「OK」ボタンではありません）をタップすれば
     インストールできます
5. 開発サーバーを起動し、インストールしたアプリから接続
   ```bash
   npx expo start --dev-client
   ```
6. インストールしたアプリを開き、「Scan QR Code」でPCに表示されたQRコードを
   読み取って接続

`eas.json` に `development` / `preview` / `production` の3プロファイルを
用意済みです。他の人に配布する場合は `preview` プロファイルで
スタンドアロンAPKをビルドしてください（`expo start --dev-client`への接続が
不要になります。ただしGoogle Play プロテクトの警告は同様に出ます）。

## 注意

- バックエンド側の Windows ファイアウォールでポート8000への
  インバウンド接続を許可しておく必要があります
- HTTP（非暗号化）通信のため、開発用ネットワーク以外では使用しないでください
- Expo SDK は意図的に **54** に固定しています。Play Store / App Store の
  Expo Go アプリが対応しているのが SDK 54 までのため（2026年半ば時点、
  新しいSDKは審査待ち）。`npx expo install --fix` 等で最新版に上げると
  「Project is incompatible with this version of Expo Go」エラーが再発します
