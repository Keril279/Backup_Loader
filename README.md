# Backup Uploader - Скрипт для резервного копирования в Google Drive / Google Drive Backup Script

## Описание / Description  
**Backup Uploader** - это скрипт на Python, который автоматически создает резервные копии указанных папок и загружает их в Google Drive. Скрипт поддерживает различные типы бэкапов (ежедневные, еженедельные, месячные, годовые) и автоматически удаляет старые копии согласно заданным правилам.  

**Backup Uploader** is a Python script that automatically creates backups of specified folders and uploads them to Google Drive. The script supports different backup types (daily, weekly, monthly, yearly) and automatically removes old backups according to configured rules.  

## Особенности / Features  
- Поддержка различных типов бэкапов / Multiple backup types support:  
  - Ежедневные / Daily  
  - Еженедельные / Weekly  
  - Ежемесячные / Monthly  
  - Годовые / Yearly  
- Автоматическая ротация старых бэкапов / Automatic old backups rotation  
- Сжатие в ZIP-архив перед загрузкой / ZIP compression before upload  
- Поддержка .env файла для конфигурации / .env file support for configuration  
- Авторизация через OAuth 2.0 / OAuth 2.0 authentication  
- Логирование процесса / Process logging  

## Технологии / Technologies  
- Python 3  
- Google Drive API v3  
- OAuth 2.0  
- dotenv (для конфигурации / for configuration)  
- argparse (для аргументов командной строки / for command line arguments)  
- zipfile (для создания архивов / for archive creation)  

## Установка / Installation  
1. Клонировать репозиторий / Clone repository  
2. Установить зависимости / Install dependencies: `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv`
3. Создать файл credentials.json (получить из Google Cloud Console) / Create or get credentials.json from Google Cloud Console
4. Создать .env файл (опционально) / Create .env file (optional):
  ```
  BACKUP_FOLDER=path_to_folder_to_backup
  TARGET_FOLDER=target_folder_name_in_google_drive
  CREDENTIALS_FILE=path_to_credentials.json
  KEEP_ORIGINALS=True/False
  ```

## Использование / Usage  
### Командная строка / Command line: 
  `python BackUp_Uploader.py --folder "path_to_backup" --target "Drive_Folder_Name" [--keep]`
  или / or  
  `python BackUp_Uploader.py (использует настройки из .env / uses settings from .env)`

### Параметры / Arguments:  
  - `--folder`: Путь к папке для резервного копирования / Path to folder to backup  
  - `--target`: Имя целевой папки в Google Drive / Target folder name in Google Drive  
  - `--credentials`: Путь к файлу credentials.json / Path to credentials.json  
  - `--keep`: Сохранять исходные файлы после загрузки / Keep original files after upload  

## Логика ротации бэкапов / Backup Rotation Logic  
  - Ежедневные бэкапы / Daily backups: сохраняются последние 7 копий / keeps last 7 copies  
  - Еженедельные бэкапы / Weekly backups: сохраняются последние 4 копии / keeps last 4 copies  
  - Ежемесячные бэкапы / Monthly backups: сохраняются последние 6 копий / keeps last 6 copies  
  - Годовые бэкапы / Yearly backups: не удаляются автоматически / not automatically deleted  

## Структура в Google Drive / Google Drive Structure
Target_Folder/
└── Source_Folder_Name/
├── Daily/
├── Weekly/
├── Monthly/
└── Yearly/
