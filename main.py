import os
import json
import logging
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from google.cloud import secretmanager

# 日本時間タイムゾーン設定
JST = timezone(timedelta(hours=9))

# ログ設定（日本時間対応）
class JSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, JST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S JST')

# ログハンドラーの設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = JSTFormatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class FitbitToObsidianSync:
    """FitbitデータをObsidianに同期するクラス"""
    
    def __init__(self):
        self.fitbit_client_id = os.environ.get('FITBIT_CLIENT_ID')
        self.fitbit_client_secret = os.environ.get('FITBIT_CLIENT_SECRET')
        self.fitbit_refresh_token = os.environ.get('FITBIT_REFRESH_TOKEN')
        self.fitbit_auth_code = os.environ.get('FITBIT_AUTH_CODE')  # 初回セットアップ用認証コード
        self.webdav_url = os.environ.get('WEBDAV_URL')
        self.webdav_username = os.environ.get('WEBDAV_USERNAME')
        self.webdav_password = os.environ.get('WEBDAV_PASSWORD')
        self.webdav_path = os.environ.get('WEBDAV_PATH')
        self.fitbit_heading_template = os.environ.get('FITBIT_HEADING_TEMPLATE', '## 📊 Fitbitデータ ({date})')
        self.daily_note_filename_format = os.environ.get('DAILY_NOTE_FILENAME_FORMAT', '📅{date}({weekday}).md')
        
        # 必須環境変数の検証
        if not self.webdav_url:
            logger.error("WEBDAV_URL環境変数が設定されていません")
        if not self.webdav_username:
            logger.error("WEBDAV_USERNAME環境変数が設定されていません")
        if not self.webdav_password:
            logger.error("WEBDAV_PASSWORD環境変数が設定されていません")
        if not self.webdav_path:
            logger.error("WEBDAV_PATH環境変数が設定されていません")
        
        logger.info(f"WebDAV設定: URL={self.webdav_url}, PATH={self.webdav_path}")
        
        # Google Cloud設定
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'fibit2obsidian')
        self.secret_name = 'fitbit-refresh-token'
        
        # Secret Managerクライアント初期化
        self.secret_client = secretmanager.SecretManagerServiceClient()
        
        # 日本語曜日マッピング
        self.weekdays_jp = {
            0: '月', 1: '火', 2: '水', 3: '木', 4: '金', 5: '土', 6: '日'
        }
        
        # Fitbit APIのベースURL
        self.fitbit_api_base = 'https://api.fitbit.com/1/user/-'
        
        # アクセストークン（実行時に取得）
        self.access_token = None
    
    def get_refresh_token_from_secret_manager(self) -> Optional[str]:
        """Secret Managerからリフレッシュトークンを取得"""
        try:
            secret_path = f"projects/{self.project_id}/secrets/{self.secret_name}/versions/latest"
            response = self.secret_client.access_secret_version(request={"name": secret_path})
            token = response.payload.data.decode("UTF-8")
            logger.info("Secret Managerからリフレッシュトークンを取得しました")
            return token
        except Exception as e:
            logger.warning(f"Secret Managerからのトークン取得に失敗: {e}")
            # フォールバック: 環境変数から取得
            return self.fitbit_refresh_token
    
    def save_refresh_token_to_secret_manager(self, new_refresh_token: str) -> bool:
        """新しいリフレッシュトークンをSecret Managerに保存"""
        try:
            # シークレットが存在しない場合は作成
            try:
                parent = f"projects/{self.project_id}"
                secret_id = self.secret_name
                secret = {"replication": {"automatic": {}}}
                self.secret_client.create_secret(
                    request={"parent": parent, "secret_id": secret_id, "secret": secret}
                )
                logger.info(f"新しいシークレット '{self.secret_name}' を作成しました")
            except Exception:
                # シークレットが既に存在する場合は無視
                pass
            
            # 新しいバージョンを追加
            parent = f"projects/{self.project_id}/secrets/{self.secret_name}"
            payload = {"data": new_refresh_token.encode("UTF-8")}
            self.secret_client.add_secret_version(
                request={"parent": parent, "payload": payload}
            )
            logger.info("新しいリフレッシュトークンをSecret Managerに保存しました")
            return True
        except Exception as e:
            logger.error(f"Secret Managerへのトークン保存に失敗: {e}")
            return False
    
    def _setup_initial_refresh_token(self) -> None:
        """初回セットアップ: 認証コードからリフレッシュトークンを取得してSecret Managerに保存"""
        try:
            logger.info(f"認証コード: {self.fitbit_auth_code[:10]}... を使用してリフレッシュトークンを取得中")
            
            # 認証コードをリフレッシュトークンに交換
            token_url = "https://api.fitbit.com/oauth2/token"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": self._get_basic_auth()
            }
            data = {
                "client_id": self.fitbit_client_id,
                "grant_type": "authorization_code",
                "redirect_uri": "http://localhost",
                "code": self.fitbit_auth_code
            }
            
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            refresh_token = token_data.get('refresh_token')
            
            if not refresh_token:
                logger.error("レスポンスにリフレッシュトークンが含まれていません")
                return
            
            # Secret Managerに保存
            if self.save_refresh_token_to_secret_manager(refresh_token):
                logger.info("✅ 初回セットアップ完了: リフレッシュトークンをSecret Managerに保存しました")
                logger.info("🔄 次回デプロイ時は FITBIT_AUTH_CODE 環境変数を削除してください")
            else:
                logger.error("❌ 初回セットアップ失敗: Secret Managerへの保存に失敗しました")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"初回セットアップエラー: {e}")
            if e.response is not None:
                logger.error(f"Fitbit APIからのエラーレスポンス: {e.response.text}")
        except Exception as e:
            logger.error(f"初回セットアップで予期しないエラー: {e}")
    
    def refresh_access_token(self) -> Optional[str]:
        """アクセストークンをリフレッシュ"""
        # まずSecret Managerから最新のリフレッシュトークンを取得
        current_refresh_token = self.get_refresh_token_from_secret_manager()
        if not current_refresh_token:
            logger.error("リフレッシュトークンが取得できません")
            return None
        
        try:
            url = "https://api.fitbit.com/oauth2/token"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {self._get_basic_auth()}'
            }
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': current_refresh_token
            }
            
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            access_token = token_data.get('access_token')
            new_refresh_token = token_data.get('refresh_token')
            
            # 新しいリフレッシュトークンが発行された場合、Secret Managerに保存
            if new_refresh_token and new_refresh_token != current_refresh_token:
                self.save_refresh_token_to_secret_manager(new_refresh_token)
                logger.info("リフレッシュトークンが更新されました")
            
            logger.info("アクセストークンのリフレッシュが成功しました")
            return access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"トークンリフレッシュエラー: {e}")
            if e.response is not None:
                logger.error(f"Fitbit APIからのエラーレスポンス: {e.response.text}")
            return None
    
    def _get_basic_auth(self) -> str:
        """Basic認証用のエンコードされた文字列を生成"""
        import base64
        credentials = f"{self.fitbit_client_id}:{self.fitbit_client_secret}"
        return base64.b64encode(credentials.encode()).decode()
    
    def get_fitbit_data(self, date: str) -> Dict[str, Any]:
        """指定日のFitbitデータを取得"""
        if not self.access_token:
            self.access_token = self.refresh_access_token()
            if not self.access_token:
                raise Exception("アクセストークンの取得に失敗しました")
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        # 取得するデータの種類
        endpoints = {
            'steps': f'{self.fitbit_api_base}/activities/steps/date/{date}/1d.json',
            'distance': f'{self.fitbit_api_base}/activities/distance/date/{date}/1d.json',
            'calories': f'{self.fitbit_api_base}/activities/calories/date/{date}/1d.json',
            'active_minutes': f'{self.fitbit_api_base}/activities/minutesVeryActive/date/{date}/1d.json',
            'sleep': f'{self.fitbit_api_base}/sleep/date/{date}.json'
        }
        
        data = {}
        
        for key, url in endpoints.items():
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 401:  # トークン期限切れ
                    logger.info("トークンが期限切れです。リフレッシュします。")
                    self.access_token = self.refresh_access_token()
                    if self.access_token:
                        headers = {'Authorization': f'Bearer {self.access_token}'}
                        response = requests.get(url, headers=headers)
                    else:
                        logger.error("トークンリフレッシュに失敗しました")
                        continue
                
                response.raise_for_status()
                data[key] = response.json()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"{key}データの取得に失敗: {e}")
                data[key] = None
        
        return data
    
    def format_data_to_markdown(self, fitbit_data: Dict[str, Any], date: datetime) -> str:
        """FitbitデータをMarkdown形式に整形"""
        # 日本語曜日を取得
        weekday_jp = self.weekdays_jp[date.weekday()]
        date_str = date.strftime('%Y-%m-%d')
        
        markdown_content = f"\n{self.fitbit_heading_template.format(date=date_str)}\n"
        markdown_content += f"*更新時刻: {datetime.now(JST).strftime('%H:%M')}*\n\n"
        
        # 歩数データ
        if fitbit_data.get('steps') and 'activities-steps' in fitbit_data['steps']:
            steps_data = fitbit_data['steps']['activities-steps'][0]
            steps = int(steps_data.get('value', '0'))
            markdown_content += f"🚶‍♂️ **歩数**: {steps:,} 歩\n"
        
        # 距離データ
        if fitbit_data.get('distance') and 'activities-distance' in fitbit_data['distance']:
            distance_data = fitbit_data['distance']['activities-distance'][0]
            distance = float(distance_data.get('value', '0'))
            markdown_content += f"📏 **距離**: {distance:.2f} km\n"
        
        # カロリーデータ
        if fitbit_data.get('calories') and 'activities-calories' in fitbit_data['calories']:
            calories_data = fitbit_data['calories']['activities-calories'][0]
            calories = int(calories_data.get('value', '0'))
            markdown_content += f"🔥 **消費カロリー**: {calories:,} kcal\n"
        
        # アクティブ時間
        if fitbit_data.get('active_minutes') and 'activities-minutesVeryActive' in fitbit_data['active_minutes']:
            active_data = fitbit_data['active_minutes']['activities-minutesVeryActive'][0]
            active_minutes = int(active_data.get('value', '0'))
            markdown_content += f"⚡ **高強度アクティブ時間**: {active_minutes} 分\n"
        
        # 睡眠データ
        if fitbit_data.get('sleep') and fitbit_data['sleep'].get('sleep'):
            sleep_data = fitbit_data['sleep']['sleep'][0] if fitbit_data['sleep']['sleep'] else None
            if sleep_data:
                sleep_minutes = sleep_data.get('minutesAsleep', 0)
                sleep_hours = sleep_minutes // 60
                sleep_mins = sleep_minutes % 60
                markdown_content += f"😴 **睡眠時間**: {sleep_hours}時間{sleep_mins}分\n"
        
        return markdown_content.rstrip() + '\n\n'
    
    def get_daily_note_filename(self, date: datetime) -> str:
        """デイリーノートのファイル名を生成"""
        weekday_jp = self.weekdays_jp[date.weekday()]
        return self.daily_note_filename_format.format(
            date=date.strftime('%Y-%m-%d'),
            weekday=weekday_jp
        )
    
    def webdav_request(self, method: str, path: str, data: bytes = None) -> requests.Response:
        """WebDAVリクエストを送信"""
        if not self.webdav_url:
            raise ValueError("WEBDAV_URL環境変数が設定されていません")
        
        url = f"{self.webdav_url.rstrip('/')}/{path.lstrip('/')}"
        auth = (self.webdav_username, self.webdav_password)
        
        headers = {}
        if method in ['PUT', 'POST'] and data:
            headers['Content-Type'] = 'text/plain; charset=utf-8'
        
        logger.info(f"-- WebDAV Request --")
        logger.info(f"  Method: {method}")
        logger.info(f"  URL: {url}")
        logger.info(f"  Auth User: {self.webdav_username}")
        logger.info(f"--------------------")

        response = requests.request(method, url, auth=auth, headers=headers, data=data)
        return response
    
    def get_existing_note(self, filename: str) -> Optional[str]:
        """既存のデイリーノートを取得"""
        try:
            path = f"{self.webdav_path.rstrip('/')}/{filename}"
            response = self.webdav_request('GET', path)
            
            if response.status_code == 200:
                logger.info(f"既存ノート発見: {filename}")
                return response.text
            elif response.status_code == 404:
                logger.info(f"既存ノートなし: {filename}")
                return None
            else:
                response.raise_for_status()
        except Exception as e:
            logger.error(f"ノート取得エラー: {e}")
            return None
    
    def save_note(self, filename: str, content: str) -> bool:
        """デイリーノートを保存"""
        try:
            path = f"{self.webdav_path.rstrip('/')}/{filename}"
            encoded_content = content.encode('utf-8')
            response = self.webdav_request('PUT', path, data=encoded_content)
            
            if response.status_code in [201, 204]: # 201: Created, 204: No Content (Updated)
                logger.info(f"ノート保存成功: {filename}")
                return True
            else:
                logger.error(f"ノート保存エラー: {response.status_code} - {response.text}")
                response.raise_for_status()
                return False
        except Exception as e:
            logger.error(f"ノート保存エラー: {e}")
            return False
    
    def sync_data(self) -> Dict[str, Any]:
        """メインの同期処理"""
        try:
            # 初回セットアップ処理（認証コードが設定されている場合）
            if self.fitbit_auth_code:
                logger.info("🔧 初回セットアップ: 認証コードからリフレッシュトークンを取得します")
                self._setup_initial_refresh_token()
                # セットアップ完了後は処理を終了（次回実行時に通常の同期処理が動作）
                return {
                    'success': True,
                    'message': '初回セットアップが完了しました。次回デプロイ時はFITBIT_AUTH_CODE環境変数を削除してください。',
                    'setup_completed': True
                }
            
            # 直近3日分のデータを同期
            now = datetime.now(JST)
            logger.info(f"Fitbitデータ同期開始: 直近3日分 ({now.strftime('%Y-%m-%d')}から過去3日)")
            
            sync_results = []
            all_success = True
            
            # 直近3日分をループ処理
            for days_ago in range(3):
                target_date = now - timedelta(days=days_ago)
                date_str = target_date.strftime('%Y-%m-%d')
                
                logger.info(f"📅 {date_str} のデータを処理中...")
                
                try:
                    # Fitbitデータを取得
                    fitbit_data = self.get_fitbit_data(date_str)
                    
                    # Markdownに整形
                    markdown_content = self.format_data_to_markdown(fitbit_data, target_date)
                    
                    # ファイル名を生成
                    filename = self.get_daily_note_filename(target_date)
                    
                    # 既存のノートを取得
                    existing_content = self.get_existing_note(filename)
                    
                    if existing_content:
                        # 既存のFitbitデータセクションを探して置き換える
                        lines = existing_content.split('\n')
                        new_lines = []
                        fitbit_section_found = False
                        fitbit_section_start = -1
                        fitbit_section_end = -1
                        
                        # FITBIT_HEADING_TEMPLATEから日付部分を除いた基本見出しを生成
                        base_heading = self.fitbit_heading_template.replace(' ({date})', '').replace('({date})', '')
                        
                        # 既存のFitbitセクションを探す
                        for i, line in enumerate(lines):
                            if line.strip().startswith(base_heading):
                                fitbit_section_found = True
                                fitbit_section_start = i
                                logger.info(f"  既存のFitbitセクションを発見: 行{i+1}")
                                break
                        
                        if fitbit_section_found:
                            # Fitbitセクションの終了位置を探す（次の見出しまたはファイル末尾）
                            for i in range(fitbit_section_start + 1, len(lines)):
                                if lines[i].strip().startswith('## ') or lines[i].strip().startswith('# '):
                                    fitbit_section_end = i
                                    break
                            
                            if fitbit_section_end == -1:
                                fitbit_section_end = len(lines)
                            
                            # 既存のFitbitセクションを新しいデータで置き換え
                            new_lines = lines[:fitbit_section_start]
                            new_lines.extend(markdown_content.rstrip('\n').split('\n'))
                            new_lines.append('')  # 空行を追加してスペースを確保
                            new_lines.extend(lines[fitbit_section_end:])
                            
                            final_content = '\n'.join(new_lines)
                            logger.info(f"  {filename}: 既存のFitbitセクションを更新")
                        else:
                            # 既存のFitbitセクションが見つからない場合は末尾に追加
                            final_content = existing_content.rstrip() + '\n\n' + markdown_content.strip()
                            logger.info(f"  {filename}: 末尾に新規Fitbitセクションを追加")
                    else:
                        # 新規ノート作成
                        header = f"# {target_date.strftime('%Y年%m月%d日')}({self.weekdays_jp[target_date.weekday()]})\n\n"
                        final_content = header + markdown_content
                        logger.info(f"  {filename}: 新規ノートを作成")
                    
                    # ノートを保存
                    success = self.save_note(filename, final_content)
                    
                    sync_results.append({
                        'date': date_str,
                        'filename': filename,
                        'success': success
                    })
                    
                    if not success:
                        all_success = False
                        logger.error(f"  {filename}: 保存に失敗")
                    else:
                        logger.info(f"  {filename}: 保存完了")
                
                except Exception as e:
                    logger.error(f"  {date_str} の処理中にエラー: {e}")
                    sync_results.append({
                        'date': date_str,
                        'filename': f"📅{date_str}({self.weekdays_jp[target_date.weekday()]}).md",
                        'success': False,
                        'error': str(e)
                    })
                    all_success = False
            
            # 全体の結果をまとめる
            result = {
                'success': all_success,
                'sync_count': len(sync_results),
                'results': sync_results,
                'message': f'直近3日分のデータ同期{"完了" if all_success else "一部失敗"}'
            }
            
            logger.info(f"全体の同期結果: {result['message']} ({len([r for r in sync_results if r['success']])}/{len(sync_results)}件成功)")
            return result
            
        except Exception as e:
            logger.error(f"同期処理エラー: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'データ同期中にエラーが発生しました'
            }


def fitbit_sync_handler(request):
    """Google Cloud Functions のエントリーポイント"""
    try:
        # CORS対応
        if request.method == 'OPTIONS':
            headers = {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Max-Age': '3600'
            }
            return ('', 204, headers)
        
        # 同期処理を実行
        sync = FitbitToObsidianSync()
        result = sync.sync_data()
        
        # レスポンスヘッダー
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        return (json.dumps(result, ensure_ascii=False), 200, headers)
        
    except Exception as e:
        logger.error(f"関数実行エラー: {e}")
        error_result = {
            'success': False,
            'error': str(e),
            'message': '関数実行中にエラーが発生しました'
        }
        
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Content-Type': 'application/json; charset=utf-8'
        }
        
        return (json.dumps(error_result, ensure_ascii=False), 500, headers)
