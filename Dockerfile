# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем директорию для постов
RUN mkdir -p posts

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Открываем порт
EXPOSE 8080

# Команда запуска
CMD ["python", "telegram_post_bot.py"]
