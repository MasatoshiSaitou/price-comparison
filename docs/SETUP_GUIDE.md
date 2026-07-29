# 労働災害防止音声会話アプリ - 環境構築ガイド

このドキュメントは、`safety-brief-backend`（FastAPIバックエンド）と
`safety-brief-app`（Expoスマホアプリ）を、**Windows PC上でゼロから構築する際に
実際に発生したトラブルとその対処法**をまとめたものです。同じ手順で作業する人が
同じ失敗を繰り返さないことを目的としています。

対象読者: Windows + PowerShellで、Python/Node.jsの開発環境をこれから作る人。
「何が起きて、なぜ起きて、どう直したか」を中心に書いています。単なる手順書
ではなく、**トラブルシューティング集**として使ってください。

---

## 全体構成（先に把握しておくこと）

```
price-comparison/
├── safety-brief-backend/   FastAPI バックエンド（Python）
│   ├── venv/                本体用の仮想環境
│   ├── main.py
│   ├── data/incident_db.json   実データ（無ければダミーDBにフォールバック）
│   └── scripts/              実データ抽出・変換用スクリプト（別のvenvで使う）
├── safety-brief-app/        Expo (React Native) スマホアプリ（Node.js）
└── render.yaml               クラウドデプロイ設定（Render）
```

**重要な原則**:
- Python（`pip`, `venv`, `uvicorn`）と Node.js（`npm`, `npx`, `expo`）は
  完全に別物です。Node.jsのコマンドを打つのにPythonのvenvは一切関係ありません
- 目的の違うPythonパッケージ（本体用 vs データ処理用）は、**別々のvenvに分ける**
  こと。同じvenvに全部入れると、後述のバージョン衝突が起きます

---

## 1. PowerShellの実行ポリシーエラー（最頻出）

### 症状
```
venv\Scripts\Activate.ps1 : このシステムではスクリプトの実行が無効になっているため、
ファイル ...\Activate.ps1 を読み込むことができません。
```
`npx` コマンドでも同じ `PSSecurityException` が出ることがあります
（`npx.ps1` も同じくPowerShellスクリプトのため）。

### 原因
Windowsの既定設定では、PowerShellでのスクリプト実行がブロックされています。
`venv`の有効化も`npx`も、内部的には`.ps1`スクリプトを実行するため引っかかります。

### 対処法（その場しのぎ・安全）
新しいPowerShellウィンドウを開くたびに、最初に実行:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```
**このウィンドウだけ**に効くので、ウィンドウを閉じるとまた同じエラーが出ます。
実際、このセッションでは新しいウィンドウを開くたびに何度もこのエラーを
踏みました。

### 対処法（恒久的・推奨）
毎回打つのが面倒なら、管理者権限のPowerShellで一度だけ実行:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```
`RemoteSigned`は「自分のPC上で書いたスクリプトは実行可、ネットからダウン
ロードした未署名スクリプトはブロック」という一般的でバランスの良い設定です。
これを最初にやっておけば、以降このエラーとは無縁になります。

---

## 2. venvの基本操作（迷いやすいポイント）

```powershell
# 作成
python -m venv venv

# 有効化（実行ポリシーエラーが出たら1.の対処を先に）
venv\Scripts\Activate.ps1

# 有効化されているか確認: プロンプトの先頭に (venv) と出る

# 無効化（元のvenvに戻さず抜けるとき）
deactivate
```
`deactivate`に引数は不要です。「今どのvenvにいるか分からなくなった」ときは、
まず`deactivate`してから入り直すのが安全です。

### 目的別にvenvを分ける（重要）

このプロジェクトでは以下の2つを**別々のvenv**にしました:

| venv | 用途 | 主なパッケージ |
| --- | --- | --- |
| `safety-brief-backend/venv` | バックエンド本体の実行 | fastapi, uvicorn, anthropic, sentence-transformers, numpy等 |
| `safety-brief-backend/scripts/venv-data` | 実データ抽出スクリプトの実行 | openpyxl（pandasは使わない、理由は4.参照） |

**同じvenvに両方入れてしまうと何が起きるか**: 本体用に慎重に選んだ
`numpy==1.24.3`（`torch`/`sentence-transformers`と相性確認済み）が、
データ処理用ライブラリのインストールで`numpy 2.x`に勝手に上書きされ、
本体の動作が不安定になる恐れがあります。実際にこのセッションでもこれが
起き、`numpy`を手動で戻す作業が発生しました。

---

## 3. git pull が package.json / package-lock.json で失敗する

### 症状
```
error: Your local changes to the following files would be overwritten by merge:
        safety-brief-app/package-lock.json
Please commit your changes or stash them before you merge.
```

### 原因
ローカルで`npm install`を実行すると、`package-lock.json`（時には
`package.json`も）の中身がわずかに書き換わることがあります（npmのバージョン
差やフォーマット差など）。これがgitの目には「ローカルの変更」として映り、
`git pull`が「上書きしていいか分からない」と拒否します。

### 対処法
これらは自動生成ファイルなので、ローカルの変更を捨てて問題ありません
（`git pull`後に`npm install`すれば正しい内容に再生成されます）:
```powershell
git checkout -- safety-brief-app/package-lock.json safety-brief-app/package.json
git pull origin <ブランチ名>
npm install
```
このセッションでは、このパターンに**3回以上**遭遇しました。エラーが出たら
まずこれを疑ってください。

---

## 4. 企業PCのセキュリティソフトがpandasのDLLをブロック

### 症状
```
ImportError: DLL load failed while importing base: アプリケーション制御ポリシー
によってこのファイルがブロックされました。
```
`import pandas`した瞬間にクラッシュします。

### 原因
`pandas`はコンパイル済みのCython/Cバイナリ（`.pyd`ファイル）を含みます。
企業管理下のPCでは、Windows Defender Application Control（WDAC）や
類似のセキュリティ機能が、未知/低評価のバイナリを実行時にブロックすることが
あります。特に新しいバージョンのパッケージは「まだ評価が定まっていない」
としてブロックされやすい傾向があります。

### 対処法
**pandasを使わない実装に書き換える**のが最も確実です。このプロジェクトの
データ抽出スクリプト（`filter_incidents.py`）は、以下だけで書き直しました:
- CSV読み込み: 標準ライブラリの`csv`モジュール
- Excel読み込み: `openpyxl`（**純Python実装**でコンパイル済みバイナリを含まない）

同様の理由で、`numpy`を伴わない処理であれば、なるべく純Pythonの
ライブラリを選ぶと、この種のブロックを回避しやすくなります。

---

## 5. Expo SDKのバージョン不一致（Expo Goが起動しない）

### 症状
スマホでQRコードを読み込むと:
```
Project is incompatible with this version of Expo Go
This project requires a newer version of Expo Go.
```
Google Playストアで最新版に更新しても直らない。

### 原因
`npx create-expo-app`は**その時点の最新Expo SDK**でプロジェクトを作成します
（このセッションではSDK 57）。しかし、Google Play / App Storeで配布されて
いる公式Expo Goアプリは、審査の関係で**最新より2〜3世代古いSDK**にしか
対応していないことがあります（このセッションではSDK 54が上限でした）。
つまり「最新版に更新した」つもりでも、そもそも新しいSDK用のExpo Goが
ストアにまだ無いため、更新のしようがありません。

### 対処法
1. Expo Goが実際に対応している最新SDKバージョンを確認する
   （公式サイトの`expo.dev/go`や、Web検索で確認可能）
2. `package.json`の`expo`のバージョンを、そのSDKの正式版に固定する
3. React / React Native / expo-status-bar等の付随パッケージも、対応する
   バージョンに合わせる必要があります。**正確なバージョンの調べ方**:
   ```powershell
   npm install expo@<対応SDKのバージョン>
   # インストール後、以下のファイルに正しい組み合わせが書いてある
   type node_modules\expo\bundledNativeModules.json
   ```
   ここに書かれている`react`, `react-native`, `expo-status-bar`等の
   バージョンをそのまま`package.json`に反映し、`npm install`をやり直す

### 注意
新しいネイティブモジュール（例: `expo-speech-recognition`）を追加する際、
そのパッケージが対応SDKごとに別バージョン（distタグ）を公開していることが
あります。`npm view <パッケージ名> versions --json`で確認し、
`npm view <パッケージ名>` の `dist-tags` に `sdk-54` のような表記が
あれば、それを使うと確実です。

---

## 6. Google Play プロテクトがカスタムビルドAPKをブロック

### 症状
EAS Buildで作った開発ビルド（`.apk`）をスマホにインストールしようとすると:
```
Google Play プロテクト
安全ではないアプリをブロックしました
このアプリは有害な可能性があります。
[インストールする]          ← 小さいリンク
[OK]                        ← 大きいボタン
```

### 原因
Play Store外で配布された（署名済みだがPlay Store未公開の）APKは、
未知のアプリとして警告されます。開発ビルド・社内配布ビルドでは頻発します。

### 対処法
**大きい「OK」ボタンは単に警告を閉じるだけ**でインストールされません。
警告文の下にある**小さい「インストールする」というテキストリンク**を
タップしてください。これが「警告を無視して続行する」ボタンです。
見落としやすいので要注意です。

---

## 7. Renderへのデプロイ時、Pythonバージョンの罠

### 症状
Renderのビルドログで:
```
ERROR: Exception:
...
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.build_meta'
```
`numpy`のような、古い/固定バージョンでピン留めしたパッケージのビルド中に
発生します。

### 原因
Renderは特に指定しない限り、その時点の最新Python（例: 3.14）を自動選択
します。しかし`numpy==1.24.3`のような2023年当時のパッケージには、最新
Python向けのビルド済みwheelがまだ存在しません。pipはソースからビルド
しようとしますが、そのために必要な`setuptools`のビルドバックエンドが
うまく解決できず失敗します。

### 対処法
Pythonバージョンを、動作確認済みのバージョン（例: 3.11）に明示的に固定
します。`render.yaml`の`envVars`に追加:
```yaml
envVars:
  - key: PYTHON_VERSION
    value: 3.11.9
```
一つ一つの依存パッケージのwheel対応状況を追いかけるより、確実で速い
解決法です。

### 補足: クラウド用requirements.txtは軽量に
`sentence-transformers` / `torch`は数百MB〜GB級で、無料プランのメモリ
制限に収まらない可能性が高いです。クラウド用には`requirements-cloud.txt`
として別ファイルを用意し、これらを含めない軽量構成にしました。埋め込み
モデルが読み込めない場合は自動でキーワード類似度にフォールバックする
設計にしてあるので、コード変更なしでそのまま動作します。

---

## 8. EAS Build（カスタム開発ビルド）関連

### 8-1. `expo-dev-client`パッケージの入れ忘れ
`eas.json`で`developmentClient: true`を設定しても、それだけでは
不十分です。実際に「開発ビルドらしい」画面（Metro接続画面等）を出す
には、`expo-dev-client`パッケージ自体をインストールする必要があります:
```powershell
npm install expo-dev-client@<SDKに対応するバージョン>
```
（対応バージョンは5.のときと同様に`bundledNativeModules.json`で確認）

これを忘れると、ビルドは成功するものの、アプリを開いたときに期待した
Development Build用の画面が出ません。

### 8-2. ネイティブモジュールをExpo Goでも壊さず使う
`expo-speech-recognition`のようなネイティブモジュールは、Expo Goでは
リンクされていないため、**通常の`import`文で読み込んだ瞬間にアプリ全体が
クラッシュ**します（`requireNativeModule`が例外を投げるため）。
```js
// NGな例（Expo Goで即クラッシュする）
import { ExpoSpeechRecognitionModule } from 'expo-speech-recognition';

// OKな例（例外を捕まえられる）
let ExpoSpeechRecognitionModule = null;
try {
  ExpoSpeechRecognitionModule = require('expo-speech-recognition').ExpoSpeechRecognitionModule;
} catch {
  // Expo Goなど、ネイティブモジュールが無い環境
}
```
静的な`import`文はJavaScriptの仕様上、実行前に巻き上げられるため
`try/catch`で囲めません。動的な`require()`に変えることで、カスタム
ビルドが無い間もアプリの他の機能（テキスト入力・音声読み上げ等）を
Expo Goで動かし続けられます。

### 8-3. EASアカウント・ログイン
```powershell
npx eas-cli login          # ブラウザでの認証が必要
npx eas-cli build:configure # 初回のみ、プロジェクトをEASに登録
npx eas-cli build --profile development --platform android
```
ビルドは**Expoのクラウド上**で実行されます。PCのスペックはビルド時間に
一切関係ありません（PCはソースのアップロードとログ表示をするだけ）。
初回ビルドは10〜20分程度かかります。

「Install and run the Android build on an emulator?」と聞かれた場合、
PCにAndroid Studio（`adb`）が無ければ`n`（no）と答えてください。
代わりに、ビルド完了後に表示されるQRコード/リンクをスマホで読み取って
インストールします。

---

## トラブルシューティング早見表

| エラーメッセージ（一部） | 章 |
| --- | --- |
| `このシステムではスクリプトの実行が無効になっている` | 1 |
| `Your local changes ... would be overwritten by merge` (package.json系) | 3 |
| `アプリケーション制御ポリシーによってこのファイルがブロックされました` | 4 |
| `Project is incompatible with this version of Expo Go` | 5 |
| `安全ではないアプリをブロックしました`（Google Play プロテクト） | 6 |
| `Cannot import 'setuptools.build_meta'`（Renderのビルド） | 7 |
| ビルドは成功するがDevelopment Build画面が出ない | 8-1 |
| Expo Goでアプリが起動直後にクラッシュする | 8-2 |

---

## まとめ: 次に同じ構成を作るなら

1. 最初に`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force`を一度実行しておく（1.）
2. Python用venvは目的別に分ける。pandasは避け、`csv`/`openpyxl`で代用する（2., 4.）
3. Expoプロジェクトは、作成直後に`bundledNativeModules.json`で対応SDKのパッケージバージョンを確認し、Play Store版Expo Goが対応しているSDKに固定する（5.）
4. クラウドデプロイ（Render等）では、Pythonバージョンを明示的に固定する（7.）
5. ネイティブモジュールを追加する際は、`require()`＋`try/catch`でExpo Go互換性を壊さないようにする（8-2）

このガイドに沿って進めれば、今回発生したトラブルの大部分は事前に回避できるはずです。
