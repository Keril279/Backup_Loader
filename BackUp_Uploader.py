# -*- coding: cp1251 -*-
import os
import sys
import io
import time
import argparse
import zipfile
import tempfile
import locale
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

if sys.platform == 'win32':
    import io
    import locale
    
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
    os.environ["PYTHONUTF8"] = "1"

def load_environment():
    encodings = ['utf-8', 'cp1251', 'utf-16']
    for encoding in encodings:
        try:
            load_dotenv('.env', encoding=encoding)
            print(f"Успешно загружен .env в кодировке {encoding}")
            return
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"Ошибка загрузки .env: {e}")
            raise
    
    raise UnicodeDecodeError("Не удалось загрузить .env ни в одной из кодировок: utf-8, cp1251, utf-16")

def parse_arguments():
    parser = argparse.ArgumentParser(description='Backup folders to Google Drive')
    parser.add_argument('--folder', type=str, help='Path to folder to backup')
    parser.add_argument('--target', type=str, help='Target folder name in Google Drive')
    parser.add_argument('--credentials', type=str, help='Path to credentials.json', default='credentials.json')
    parser.add_argument('--keep', action='store_true', help='Keep original files after upload')
    return parser.parse_args()

def get_token_path():
    if getattr(sys, 'frozen', False):
        script_dir = Path(sys.executable).parent
    else:
        script_dir = Path(__file__).parent
    return script_dir / 'token.json'

def get_config(args):
    config = {
        'BACKUP_FOLDER': args.folder or os.getenv("BACKUP_FOLDER"),
        'TARGET_FOLDER': args.target or os.getenv("TARGET_FOLDER", "Uni_Backups"),
        'CREDENTIALS_FILE': args.credentials or os.getenv("CREDENTIALS_FILE"),
        'SCOPES': ['https://www.googleapis.com/auth/drive.file'],
        'KEEP_ORIGINALS': args.keep if args.keep is not None else bool(os.getenv("KEEP_ORIGINALS", False))
    }
    
    if not config['BACKUP_FOLDER']:
        raise ValueError("Backup folder not specified (use --folder or set BACKUP_FOLDER in .env)")
    if not config['CREDENTIALS_FILE']:
        raise ValueError("Credentials file not specified (use --credentials or set CREDENTIALS_FILE in .env)")
    if not os.path.exists(config['CREDENTIALS_FILE']):
        raise FileNotFoundError(f"Credentials file not found at: {config['CREDENTIALS_FILE']}")
    
    return config

def safe_remove(filepath, max_retries=3, delay=1):
    for i in range(max_retries):
        try:
            os.remove(filepath)
            return True
        except (PermissionError, OSError) as e:
            if i == max_retries - 1:
                print(f"Failed to remove file {filepath}: {e}")
                return False
            time.sleep(delay)
    return False

def authenticate(credentials_file, scopes):
    token_file = str(get_token_path()) 
    try:
        if os.path.exists(token_file):
            if not os.access(token_file, os.W_OK):
                raise PermissionError(f"No write permissions for {token_file}")
        
        creds = None
        if os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(token_file, scopes)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            except Exception as e:
                print(f"Ошибка загрузки токена: {e}")
                try:
                    os.remove(token_file)
                except:
                    pass
        
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, 
                scopes,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            creds = flow.run_local_server(port=0)
            
            token_dir = os.path.dirname(token_file)
            if not os.access(token_dir, os.W_OK):
                raise PermissionError(f"No write permissions for {token_dir}")
            
            with open(token_file, 'w') as token:
                token.write(creds.to_json())
        
        return creds
        
    except Exception as e:
        print(f"Ошибка аутентификации: {e}")
        raise

def get_or_create_folder(service, folder_name, parent_id=None):
    
    try:
        query = [
            f"name='{folder_name}'",
            "mimeType='application/vnd.google-apps.folder'",
            "trashed=false"
        ]
        if parent_id:
            query.append(f"'{parent_id}' in parents")
        
        results = service.files().list(
            q=" and ".join(query),
            fields="files(id,name)"
        ).execute()
        
        folders = results.get('files', [])
        if folders:
            return folders[0]['id']
        
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
        }
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        folder = service.files().create(
            body=folder_metadata,
            fields='id'
        ).execute()
        return folder.get('id')
    
    except HttpError as error:
        print(f"Google Drive API error: {error}")
        return None
    
def get_backup_type():
    today = datetime.now()
    # Если сегодня 1-е число месяца и январь - это годовой бэкап
    if today.day == 1 and today.month == 1:
        return "Yearly"
    # Если 1-е число месяца - месячный бэкап
    elif today.day == 1:
        return "Monthly"
    # Если воскресенье - недельный бэкап
    elif today.weekday() == 6:
        return "Weekly"
    # Иначе - дневной бэкап
    else:
        return "Daily"
    
def rotate_backups(service, folder_id, max_backups):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id,name,createdTime)",
            orderBy="createdTime desc"
        ).execute()
        files = results.get('files', [])
        for file in files[max_backups:]:
            service.files().delete(fileId=file['id']).execute()
            print(f"Deleted old backup: {file['name']}")

    except HttpError as error:
        print(f"Error rotating backups: {error}")

def format_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def create_backup_archive(folder_path, backup_type):
    folder_name = os.path.basename(folder_path.rstrip('/\\'))
    
    timestamp = datetime.now().strftime("%Y.%m.%d")
    zip_name = f"{folder_name} [{backup_type}] {timestamp}.zip"
    zip_path = os.path.join(tempfile.gettempdir(), zip_name)
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, start=os.path.dirname(folder_path))
                    zipf.write(file_path, arcname)
        
        archive_size = os.path.getsize(zip_path)
        print(f"Создан архив: {zip_name} ({format_size(archive_size)})")
        return zip_path
        
    except Exception as e:
        if os.path.exists(zip_path):
            safe_remove(zip_path)
        raise Exception(f"Ошибка при создании архива: {e}")
    

def upload_file(service, file_path, target_folder_id):
    file_name = (Path(file_path).name)
    print(f"Загрузка файла: {file_name}")
    
    try:
        file_metadata = {
            'name': file_name,
            'parents': [target_folder_id]
        }
        
        media = MediaFileUpload(file_path, resumable=True)
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Загружено {int(status.progress() * 100)}%")
        
        print(f"Файл успешно загружен: {file_name}")
        return True
        
    except HttpError as error:
        print(f"Ошибка загрузки: {error}")
        return False
    

def main():
    load_environment()
    args = parse_arguments()
    
    try:
        config = get_config(args)
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}")
        return
    
    print(f"Источник бэкапа: {config['BACKUP_FOLDER']}")
    print(f"Целевая папка: {config['TARGET_FOLDER']}")
    
    try:
        creds = authenticate(config['CREDENTIALS_FILE'], config['SCOPES'])
        service = build('drive', 'v3', credentials=creds)
        
        backup_type = get_backup_type()
        print(f"Тип бэкапа: {backup_type}")
        folder_name = os.path.basename(config['BACKUP_FOLDER'].rstrip('/\\'))
        root_folder_id = get_or_create_folder(service, config['TARGET_FOLDER'])
        semester_folder_id = get_or_create_folder(service, folder_name, parent_id=root_folder_id)
        target_folder_id = get_or_create_folder(service, backup_type, parent_id=semester_folder_id)
        zip_path = create_backup_archive(config['BACKUP_FOLDER'], backup_type)
        
        if upload_file(service, zip_path, target_folder_id):
            print(f"Бэкап загружен в папку '{backup_type}'")
            
            # Ротация старых бэкапов
            if backup_type == "Daily":
                rotate_backups(service, target_folder_id, max_backups=7)
            elif backup_type == "Weekly":
                rotate_backups(service, target_folder_id, max_backups=4)
            elif backup_type == "Monthly":
                rotate_backups(service, target_folder_id, max_backups=6)
        else:
            print("Ошибка загрузки бэкапа")
        if not config['KEEP_ORIGINALS']:
            safe_remove(zip_path)
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()