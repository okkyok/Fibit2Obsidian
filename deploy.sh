#!/bin/bash

# --- .env ファイルを読み込む ---
if [ -f .env ]; then
    echo "ℹ️ .envファイルを読み込んでいます..."
    set -o allexport
    source .env
    set +o allexport
else
    echo "❌ エラー: .envファイルが見つかりません。"
    exit 1
fi
# --------------------------

# Fitbit to Obsidian 同期システムのデプロイスクリプト

set -e

echo "🚀 Fitbit to Obsidian 同期システムをデプロイします..."

# 環境変数の確認
required_vars=("FITBIT_CLIENT_ID" "FITBIT_CLIENT_SECRET" "FITBIT_REFRESH_TOKEN" "WEBDAV_URL" "WEBDAV_USERNAME" "WEBDAV_PASSWORD")

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ エラー: 環境変数 $var が設定されていません"
        echo "以下のコマンドで環境変数を設定してください:"
        echo "export $var=\"your_value\""
        exit 1
    fi
done

echo "✅ 環境変数の確認完了"

# プロジェクトIDの確認
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ エラー: Google Cloudプロジェクトが設定されていません"
    echo "以下のコマンドでプロジェクトを設定してください:"
    echo "gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📋 プロジェクトID: $PROJECT_ID"

# リージョンの設定（デフォルト: asia-northeast1）
REGION=${REGION:-asia-northeast1}
echo "🌏 リージョン: $REGION"

# Cloud Functions APIの有効化
echo "🔧 必要なAPIを有効化しています..."
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable appengine.googleapis.com

echo "🔐 Secret Manager権限を設定しています..."
# Cloud FunctionのサービスアカウントにSecret Manager権限を付与
PROJECT_NUMBER=$(gcloud projects describe fibit2obsidian --format='value(projectNumber)')
SERVICE_ACCOUNT="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding fibit2obsidian \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding fibit2obsidian \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretVersionManager"

# 関数のデプロイ
echo "📦 Cloud Functionsをデプロイしています..."
gcloud functions deploy fitbit-sync \
    --runtime python312 \
    --trigger-http \
    --allow-unauthenticated \
    --entry-point fitbit_sync_handler \
    --memory 256MB \
    --timeout 540s \
    --region $REGION \
    --set-env-vars FITBIT_CLIENT_ID="$FITBIT_CLIENT_ID",FITBIT_CLIENT_SECRET="$FITBIT_CLIENT_SECRET",FITBIT_REFRESH_TOKEN="$FITBIT_REFRESH_TOKEN",FITBIT_AUTH_CODE="$FITBIT_AUTH_CODE",WEBDAV_URL="$WEBDAV_URL",WEBDAV_USERNAME="$WEBDAV_USERNAME",WEBDAV_PASSWORD="$WEBDAV_PASSWORD",WEBDAV_PATH="$WEBDAV_PATH",FITBIT_HEADING_TEMPLATE="$FITBIT_HEADING_TEMPLATE",DAILY_NOTE_FILENAME_FORMAT="$DAILY_NOTE_FILENAME_FORMAT",TZ="$TZ"

echo "✅ Cloud Functionsのデプロイ完了"

# Cloud FunctionsのURLを取得 (Gen1/Gen2両対応)
FUNCTION_URL=$(gcloud functions describe $FUNCTION_NAME --region=$REGION --format='value(url)' 2>/dev/null || gcloud functions describe $FUNCTION_NAME --region=$REGION --format='value(serviceConfig.uri)' 2>/dev/null)

if [ -z "$FUNCTION_URL" ]; then
    echo "❌ エラー: Cloud FunctionのURL取得に失敗しました。"
    echo "Google Cloudコンソールで関数の状態を確認してください。"
    exit 1
fi

echo "🔗 関数URL: $FUNCTION_URL"

# Cloud Schedulerジョブの作成（既存の場合は更新）
echo "⏰ Cloud Schedulerジョブを設定しています..."

# App Engineアプリケーションの存在確認
if ! gcloud app describe >/dev/null 2>&1; then
    echo "📱 App Engineアプリケーションを作成しています..."
    gcloud app create --region=$REGION
fi

# 既存のジョブを削除（エラーを無視）
gcloud scheduler jobs delete fitbit-sync-job --location=$REGION --quiet >/dev/null 2>&1 || true

# 新しいジョブを作成
gcloud scheduler jobs create http fitbit-sync-job \
    --schedule="0 3,7,11,15,19,23 * * *" \
    --uri="$FUNCTION_URL" \
    --http-method=POST \
    --location=$REGION \
    --time-zone="Asia/Tokyo" \
    --description="Fitbitデータを午前3時から4時間ごとに同期"

echo "✅ Cloud Schedulerジョブの設定完了"

# テスト実行
echo "🧪 テスト実行を開始します..."
curl -X POST "$FUNCTION_URL" -H "Content-Type: application/json" -d '{}' || echo "⚠️  テスト実行でエラーが発生しました（初回は正常です）"

echo ""
echo "🎉 デプロイが完了しました！"
echo ""
echo "📋 設定内容:"
echo "  - 関数名: fitbit-sync"
echo "  - リージョン: $REGION"
echo "  - スケジュール: 4時間ごと (0 */4 * * *)"
echo "  - タイムゾーン: Asia/Tokyo"
echo ""
echo "🔍 ログの確認:"
echo "  gcloud functions logs read fitbit-sync --region=$REGION --limit=50"
echo ""
echo "🔧 手動実行:"
echo "  curl -X POST \"$FUNCTION_URL\""
echo ""
echo "⏰ スケジューラーの管理:"
echo "  gcloud scheduler jobs list --location=$REGION"
echo "  gcloud scheduler jobs run fitbit-sync-job --location=$REGION"
echo ""
