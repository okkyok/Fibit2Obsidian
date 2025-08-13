# Fitbit to Obsidian 自動同期システム

FitbitのアクティビティデータをObsidianのデイリーノートに自動で同期するGoogle Cloud Functionsプロジェクトです。

## ✨ 主な機能

- **自動データ取得**: 歩数、距離、消費カロリー、アクティブ時間、睡眠時間など、Fitbitの主要なアクティビティデータを自動で取得します。
- **動的トークン管理**: Google Cloud Secret Managerと連携し、Fitbitの認証トークンを動的に管理。トークンの有効期限切れによる手動更新の手間を完全に排除しました。
- **3日間データ同期**: 実行タイミングを逃してもデータを取りこぼさないよう、常に直近3日分のデータを取得・更新します。
- **柔軟なMarkdown整形**: 見出しやファイル名の形式を環境変数で自由にカスタマイズできます。
- **WebDAV連携**: WebDAVプロトコル経由でObsidianのデイリーノートを安全に更新します。
- **自動スケジュール実行**: Google Cloud Schedulerにより、4時間ごとに自動で同期処理が実行されます。

## 🚀 セットアップ手順

### 1. 前提条件

- Google Cloud Platform (GCP) アカウント
- `gcloud` CLIがインストール・設定済みであること
- Python 3.12 環境

### 2. プロジェクトの準備

1.  このリポジトリをクローンします。
2.  `.env.example`をコピーして`.env`ファイルを作成します。

    ```bash
    cp .env.example .env
    ```

### 3. Fitbit アプリケーションの作成

1.  [Fitbit Developer Console](https://dev.fitbit.com/)にアクセスし、新しいアプリケーションを作成します。
2.  `Client ID`と`Client Secret`をメモし、`.env`ファイルに設定します。

### 4. 認証コードの取得と初回セットアップ

1.  以下のURLをブラウザで開き、Fitbitアカウントでログインしてアクセスを許可します。
    `https://www.fitbit.com/oauth2/authorize?response_type=code&client_id=【あなたのClient ID】&scope=activity+heartrate+profile+sleep+weight&redirect_uri=https%3A%2F%2Flocalhost`
2.  リダイレクト後のURLから`code`パラメータの値（これが認証コード）をコピーします。
3.  `.env`ファイルの`FITBIT_AUTH_CODE`に、取得した認証コードを設定します。

### 5. 環境変数の設定

`.env`ファイルに、FitbitとWebDAV（Obsidianの保存先）の情報を設定します。

- `GCP_PROJECT_ID`: あなたのGCPプロジェクトID
- `FITBIT_CLIENT_ID`: FitbitアプリのClient ID
- `FITBIT_CLIENT_SECRET`: FitbitアプリのClient Secret
- `FITBIT_AUTH_CODE`: 上記で取得した初回認証コード
- `WEBDAV_URL`, `WEBDAV_USERNAME`, `WEBDAV_PASSWORD`: WebDAVの接続情報
- `WEBDAV_PATH`: Obsidianデイリーノートの保存先パス
- `FITBIT_HEADING_TEMPLATE`: Fitbitデータの見出し（オプション）
- `DAILY_NOTE_FILENAME_FORMAT`: デイリーノートのファイル名形式（オプション）

### 6. デプロイ

以下のスクリプトを実行するだけで、必要なAPIの有効化、権限設定、Cloud FunctionsとCloud Schedulerのデプロイが自動で行われます。

```bash
./deploy.sh
```

デプロイが完了すると、初回実行時に認証コードを使ってリフレッシュトークンが自動的に取得され、Secret Managerに安全に保存されます。

**【重要】**
初回セットアップが完了したら、`.env`ファイルから`FITBIT_AUTH_CODE`の行を削除（または値を空に）して、再度`./deploy.sh`を実行してください。これにより、2回目以降は通常の同期処理が実行されます。

## 📁 ファイル構成

```
Fibit2Obsidian/
├── main.py              # メインの同期処理ロジック
├── requirements.txt     # Python依存関係
├── deploy.sh            # 自動デプロイスクリプト
├── .env.example         # 環境変数テンプレート
├── .gitignore           # Git管理対象外ファイル
├── README.md            # このファイル
└── test_local.py        # ローカルテスト用スクリプト（非推奨）
```

## 📝 出力形式

デイリーノートは、デフォルトで以下の形式で作成・更新されます。

**ファイル名:** `📅YYYY-MM-DD(曜日).md`

**内容:**
```markdown
# YYYY年MM月DD日(曜日)

## 📊 Fitbitデータ
*更新時刻: HH:MM*

| **アクティビティ** | データ | 単位 |
| :--- | :--- | :--- |
| 🚶‍♂️ 歩数 | 12,345 | 歩 |
| 📏 距離 | 8.50 | km |
| 🔥 消費カロリー | 2,500 | kcal |
| ⚡ 高強度アクティブ時間 | 30 | 分 |

| **睡眠** | データ | 単位 | **睡眠** | データ | 単位 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 💡 目覚めた状態 | 00:46 | hh:mm | 🌃 就寝時刻 | 23:15 | hh:mm |
| 🧠 レム睡眠 | 01:12 | hh:mm | 🌅 起床時刻 | 07:31 | hh:mm |
| 😴 浅い睡眠 | 03:04 | hh:mm | 🛌 ベッドにいた合計時間 | 08:16 | hh:mm |
| 🌌 深い睡眠 | 01:14 | hh:mm | 👀 起床回数 | 15 | 回 |
| 💤 総睡眠時間 | 06:16 | hh:mm | 🔄 寝返りの回数 | 0 | 回 |
```
```

## トラブルシューティング

### よくある問題

1. **トークンエラー**
   - Fitbitのリフレッシュトークンが期限切れの場合、新しいトークンを取得してください

2. **WebDAV接続エラー**
   - WebDAVのURL、ユーザー名、パスワードを確認してください
   - ネットワーク接続を確認してください

3. **ファイル保存エラー**
   - Obsidianヴォールト内に「Daily Notes」フォルダが存在することを確認してください

### ログの確認

```bash
# Cloud Functionsのログを確認
gcloud functions logs read fitbit-sync --limit=50
```

## カスタマイズ

### データ取得間隔の変更

`deploy.sh`内のcronスケジュールを変更：
- 毎時実行: `"0 * * * *"`
- 2時間ごと: `"0 */2 * * *"`
- 毎日実行: `"0 9 * * *"`

### 出力パスの変更

`main.py`の`save_note`メソッド内のパスを変更：
```python
path = f"Your Custom Path/{filename}"
```

## セキュリティ

- 環境変数を使用して認証情報を安全に管理
- WebDAV接続はHTTPS推奨
- Cloud Functionsのアクセス制御を適切に設定

## ライセンス

MIT License
