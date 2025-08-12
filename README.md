# Fitbit to Obsidian 自動同期システム

FitbitのアクティビティデータをObsidianのデイリーノートに自動同期するGoogle Cloud Functionsプロジェクトです。

## 機能

- 📊 Fitbit APIからアクティビティデータを取得（歩数、距離、消費カロリー、アクティブ時間、睡眠時間）
- 🔄 アクセストークンの自動リフレッシュ
- 📝 日本語曜日対応のMarkdown形式でデータを整形
- 🌐 WebDAV経由でObsidianヴォールトにファイルを保存
- ⏰ Cloud Schedulerによる4時間ごとの自動実行

## セットアップ

### 1. Fitbit Developer アプリケーションの作成

1. [Fitbit Developer Console](https://dev.fitbit.com/)にアクセス
2. 新しいアプリケーションを作成
3. 以下の情報を取得：
   - Client ID
   - Client Secret
   - Refresh Token（OAuth 2.0フローで取得）

### 2. WebDAV設定

Infinicloud WebDAVの認証情報を準備：
- WebDAV URL
- ユーザー名
- パスワード

### 3. Google Cloud Functionsへのデプロイ

#### 環境変数の設定

```bash
# 環境変数を設定
export FITBIT_CLIENT_ID="your_fitbit_client_id"
export FITBIT_CLIENT_SECRET="your_fitbit_client_secret"
export FITBIT_REFRESH_TOKEN="your_fitbit_refresh_token"
export WEBDAV_URL="https://your-webdav-server.com"
export WEBDAV_USERNAME="your_webdav_username"
export WEBDAV_PASSWORD="your_webdav_password"
```

#### デプロイコマンド

```bash
# Google Cloud CLIでログイン
gcloud auth login

# プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

# 関数をデプロイ
gcloud functions deploy fitbit-sync \
    --runtime python312 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point fitbit_sync_handler \
    --memory 256MB \
    --timeout 540s \
    --set-env-vars FITBIT_CLIENT_ID=$FITBIT_CLIENT_ID,FITBIT_CLIENT_SECRET=$FITBIT_CLIENT_SECRET,FITBIT_REFRESH_TOKEN=$FITBIT_REFRESH_TOKEN,WEBDAV_URL=$WEBDAV_URL,WEBDAV_USERNAME=$WEBDAV_USERNAME,WEBDAV_PASSWORD=$WEBDAV_PASSWORD
```

### 4. Cloud Schedulerの設定

4時間ごとに関数を実行するスケジューラーを作成：

```bash
# Cloud Schedulerジョブを作成
gcloud scheduler jobs create http fitbit-sync-job \
    --schedule="0 */4 * * *" \
    --uri="https://REGION-YOUR_PROJECT_ID.cloudfunctions.net/fitbit-sync" \
    --http-method=POST \
    --time-zone="Asia/Tokyo" \
    --description="Fitbitデータを4時間ごとに同期"
```

## ファイル構造

```
Fibit2Obsidian/
├── main.py              # メインの同期処理
├── requirements.txt     # Python依存関係
├── README.md           # このファイル
├── deploy.sh           # デプロイスクリプト
└── test_local.py       # ローカルテスト用スクリプト
```

## 出力形式

デイリーノートは以下の形式で作成・更新されます：

```markdown
# 2024年08月12日(月)

## 📊 Fitbitデータ (2024-08-12)
*更新時刻: 17:30*

🚶‍♂️ **歩数**: 8,542 歩
📏 **距離**: 6.23 km
🔥 **消費カロリー**: 2,145 kcal
⚡ **高強度アクティブ時間**: 32 分
😴 **睡眠時間**: 7時間23分

---
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
