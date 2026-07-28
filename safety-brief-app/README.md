# safety-brief-app

`safety-brief-backend` の動作確認用の最小限の Expo (React Native) アプリです。
作業内容をテキストで入力して `POST /safety-brief` を叩き、レスポンス
（安全ブリーフィングと類似災害事例）を画面に表示します。

音声入力・TTS再生はまだ実装していません（後のフェーズ）。

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

## 注意

- バックエンド側の Windows ファイアウォールでポート8000への
  インバウンド接続を許可しておく必要があります
- HTTP（非暗号化）通信のため、開発用ネットワーク以外では使用しないでください
- Expo SDK は意図的に **54** に固定しています。Play Store / App Store の
  Expo Go アプリが対応しているのが SDK 54 までのため（2026年半ば時点、
  新しいSDKは審査待ち）。`npx expo install --fix` 等で最新版に上げると
  「Project is incompatible with this version of Expo Go」エラーが再発します
