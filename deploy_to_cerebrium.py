#!/usr/bin/env python3
"""
Скрипт для деплоя на Cerebrium через API
"""
import os
import requests
import json
from pathlib import Path

# Inference Key из вашего аккаунта
INFERENCE_KEY = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJwcm9qZWN0SWQiOiJwLTA5NjYxYWFmIiwiaWF0IjoxNzU5NTk0MDIzLCJleHAiOjIwNzUxNzAwMjN9.dkFVOP3EWKOo2_ut9SmhPU463JRj-4tljgVwwfJNKvzrpgAieFdk1hWgka0LDHNmbPHjnoryiMJPKMkA1l_QKmu7GJ8MKWLNmRER4z2-BkVBXU4EnNOllRgB0rdkBL5DNWYVHj0fQGdIdr59dh7BNpj8JmzjJxYtepPotipgeFU-nhpmSukXjoBCsWtYC8QMRSrq_9gbtu2NC_EE749DMtL7slQ7YcLlUr5qHk2YKWPSiWKQ16dyhLTZmSsYwhqZ62AJzH6MsdlY7tm6NNeykUtokBvmb6W4pxjJk_JFwQmXyc3PjEP6qy5-FDdvxcREca-OM-n-WUV-sUCcQJrFsA"

def create_deployment_package():
    """Создает пакет для деплоя"""
    print("📦 Создание пакета для деплоя...")
    
    # Файлы для деплоя
    files_to_include = [
        'telegram_post_bot.py',
        'requirements.txt',
        'cerebrium.toml'
    ]
    
    package_files = {}
    
    for file_name in files_to_include:
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as f:
                package_files[file_name] = f.read()
            print(f"✅ Добавлен файл: {file_name}")
        else:
            print(f"❌ Файл не найден: {file_name}")
    
    return package_files

def deploy_to_cerebrium():
    """Деплой на Cerebrium"""
    print("🚀 Начинаем деплой на Cerebrium...")
    
    # Создаем пакет
    package_files = create_deployment_package()
    
    if not package_files:
        print("❌ Нет файлов для деплоя!")
        return False
    
    # Настройки деплоя
    deployment_config = {
        "name": "telegram-post-bot",
        "description": "Telegram bot for post management",
        "runtime": "custom",
        "entrypoint": "python telegram_post_bot.py",
        "port": 8080,
        "environment_variables": {
            "TELEGRAM_BOT_TOKEN": "8470292535:AAEnht_KLqU3zB01i_VsYzYZxn7zo1hUjI8",
            "PORT": "8080",
            "PYTHONUNBUFFERED": "1"
        },
        "files": package_files
    }
    
    print("📋 Конфигурация деплоя:")
    print(f"  - Название: {deployment_config['name']}")
    print(f"  - Entry point: {deployment_config['entrypoint']}")
    print(f"  - Порт: {deployment_config['port']}")
    print(f"  - Файлов: {len(package_files)}")
    
    # Здесь должен быть API вызов к Cerebrium
    # Но поскольку у нас есть только Inference Key, 
    # лучше использовать веб-интерфейс
    
    print("\n🌐 Для деплоя используйте веб-интерфейс:")
    print("1. Откройте https://dashboard.cerebrium.ai")
    print("2. Найдите проект с ID: p-09661aaf")
    print("3. Загрузите файлы:")
    for file_name in package_files.keys():
        print(f"   - {file_name}")
    print("4. Настройте переменные окружения:")
    for key, value in deployment_config['environment_variables'].items():
        print(f"   - {key}={value}")
    print("5. Нажмите Deploy")
    
    return True

if __name__ == "__main__":
    print("🤖 Деплой Telegram бота на Cerebrium")
    print("=" * 50)
    
    success = deploy_to_cerebrium()
    
    if success:
        print("\n✅ Инструкции по деплою готовы!")
        print("📱 После деплоя ваш бот будет доступен по URL:")
        print("   https://telegram-post-bot.cerebrium.app")
    else:
        print("\n❌ Ошибка при подготовке деплоя")
