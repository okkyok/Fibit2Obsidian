#!/usr/bin/env python3
"""
Fitbit to Obsidian 同期システムのローカルテスト用スクリプト

使用方法:
1. 環境変数を設定
2. python test_local.py を実行

環境変数:
- FITBIT_CLIENT_ID
- FITBIT_CLIENT_SECRET  
- FITBIT_REFRESH_TOKEN
- WEBDAV_URL
- WEBDAV_USERNAME
- WEBDAV_PASSWORD
"""

import os
import sys
from dotenv import load_dotenv
from main import FitbitToObsidianSync

# .envファイルから環境変数を読み込む
load_dotenv()

def check_environment():
    """環境変数の確認"""
    required_vars = [
        'FITBIT_CLIENT_ID',
        'FITBIT_CLIENT_SECRET', 
        'FITBIT_REFRESH_TOKEN',
        'WEBDAV_URL',
        'WEBDAV_USERNAME',
        'WEBDAV_PASSWORD',
        'WEBDAV_PATH'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ 以下の環境変数が設定されていません:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n設定例:")
        print("export FITBIT_CLIENT_ID='your_client_id'")
        print("export FITBIT_CLIENT_SECRET='your_client_secret'")
        print("export FITBIT_REFRESH_TOKEN='your_refresh_token'")
        print("export WEBDAV_URL='https://your-webdav-server.com'")
        print("export WEBDAV_USERNAME='your_username'")
        print("export WEBDAV_PASSWORD='your_password'")
        return False
    
    print("✅ 環境変数の確認完了")
    return True

def test_fitbit_connection():
    """Fitbit API接続テスト"""
    print("\n🔍 Fitbit API接続テスト...")
    try:
        sync = FitbitToObsidianSync()
        
        # トークンリフレッシュテスト
        if sync.refresh_fitbit_token():
            print("✅ Fitbitトークンリフレッシュ成功")
        else:
            print("❌ Fitbitトークンリフレッシュ失敗")
            return False
        
        # データ取得テスト
        from datetime import datetime
        date_str = datetime.now().strftime('%Y-%m-%d')
        data = sync.get_fitbit_data(date_str)
        
        if data:
            print("✅ Fitbitデータ取得成功")
            print(f"   取得データ: {list(data.keys())}")
        else:
            print("❌ Fitbitデータ取得失敗")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Fitbit接続エラー: {e}")
        return False

def test_webdav_connection():
    """WebDAV接続テスト"""
    print("\n🌐 WebDAV接続テスト...")
    try:
        sync = FitbitToObsidianSync()
        
        # テストファイルを作成
        test_filename = "test_connection.md"
        test_content = "# WebDAV接続テスト\n\nこのファイルは接続テスト用です。"
        
        # ファイル保存テスト
        if sync.save_note(test_filename, test_content):
            print("✅ WebDAVファイル保存成功")
        else:
            print("❌ WebDAVファイル保存失敗")
            return False
        
        # ファイル読み取りテスト
        retrieved_content = sync.get_existing_note(test_filename)
        if retrieved_content:
            print("✅ WebDAVファイル読み取り成功")
        else:
            print("❌ WebDAVファイル読み取り失敗")
            return False
        
        # テストファイルを削除
        try:
            sync.webdav_request('DELETE', f"Daily Notes/{test_filename}")
            print("✅ テストファイル削除完了")
        except:
            print("⚠️  テストファイルの削除に失敗（手動で削除してください）")
        
        return True
        
    except Exception as e:
        print(f"❌ WebDAV接続エラー: {e}")
        return False

def test_full_sync():
    """完全な同期処理テスト"""
    print("\n🔄 完全同期処理テスト...")
    try:
        sync = FitbitToObsidianSync()
        result = sync.sync_data()
        
        if result.get('success'):
            print("✅ 完全同期処理成功")
            print(f"   ファイル名: {result.get('filename')}")
            print(f"   日付: {result.get('date')}")
            print(f"   メッセージ: {result.get('message')}")
        else:
            print("❌ 完全同期処理失敗")
            print(f"   エラー: {result.get('error')}")
            print(f"   メッセージ: {result.get('message')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 完全同期処理エラー: {e}")
        return False

def main():
    """メインテスト処理"""
    print("🧪 Fitbit to Obsidian 同期システム ローカルテスト")
    print("=" * 50)
    
    # 環境変数チェック
    if not check_environment():
        sys.exit(1)
    
    # 各種テスト実行
    tests = [
        ("Fitbit API接続", test_fitbit_connection),
        ("WebDAV接続", test_webdav_connection),
        ("完全同期処理", test_full_sync)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        if test_func():
            passed += 1
            print(f"✅ {test_name}: 成功")
        else:
            print(f"❌ {test_name}: 失敗")
    
    # 結果サマリー
    print("\n" + "="*50)
    print(f"🏁 テスト結果: {passed}/{total} 成功")
    
    if passed == total:
        print("🎉 すべてのテストが成功しました！")
        print("デプロイの準備が整いました。")
        print("\n次のステップ:")
        print("1. chmod +x deploy.sh")
        print("2. ./deploy.sh")
    else:
        print("⚠️  一部のテストが失敗しました。")
        print("設定を確認してから再度テストしてください。")
        sys.exit(1)

if __name__ == "__main__":
    main()
