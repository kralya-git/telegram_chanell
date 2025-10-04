import os
import logging
import asyncio
import nest_asyncio
import time
import threading
import signal
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import Conflict, RetryAfter, TimedOut, BadRequest
from dotenv import load_dotenv
from flask import Flask, render_template_string, jsonify

# Apply nest_asyncio to handle event loop issues
nest_asyncio.apply()

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования с более подробной информацией
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),  # Вывод в консоль
        logging.FileHandler('bot.log', encoding='utf-8')  # Логи в файл
    ]
)

# Глобальный logger для использования во всем приложении
logger = logging.getLogger(__name__)

# Глобальная переменная для управления ботом
bot_instance = None
shutdown_event = threading.Event()


class PostBot:
    def __init__(self, token: str):
        self.token = token
        self.posts_dir = "posts"
        self._ensure_posts_directory()

    def _ensure_posts_directory(self):
        """Создает директорию для постов, если она не существует"""
        if not os.path.exists(self.posts_dir):
            os.makedirs(self.posts_dir)
            logger.info(f"Created posts directory: {self.posts_dir}")

    def _create_main_keyboard(self):
        """Создает главную клавиатуру с кнопкой 'Создать пост'"""
        keyboard = [
            [InlineKeyboardButton("📝 Создать пост", callback_data='create_post')],
        ]
        return InlineKeyboardMarkup(keyboard)

    def _get_next_post_number(self) -> int:
        """Получает следующий номер поста"""
        existing_posts = [d for d in os.listdir(self.posts_dir)
                         if os.path.isdir(os.path.join(self.posts_dir, d)) and d.startswith("Пост_")]
        if not existing_posts:
            return 1

        numbers = []
        for post_dir in existing_posts:
            try:
                num = int(post_dir.split("_")[1])
                numbers.append(num)
            except (IndexError, ValueError):
                continue

        return max(numbers) + 1 if numbers else 1

    def _create_post_directory(self, post_number: int) -> str:
        """Создает директорию для поста"""
        post_dir = os.path.join(self.posts_dir, f"Пост_{post_number}")
        os.makedirs(post_dir, exist_ok=True)
        return post_dir

    def _save_text_content(self, post_dir: str, text: str):
        """Сохраняет текстовый контент поста"""
        text_file = os.path.join(post_dir, "content.txt")
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        logger.info(f"Saved text content to: {text_file}")

    def _save_media_file(self, post_dir: str, file_path: str, file_name: str):
        """Сохраняет медиа файл в папку поста"""
        # Создаем уникальное имя файла, если файл с таким именем уже существует
        base_name, ext = os.path.splitext(file_name)
        counter = 1
        final_file_name = file_name
        final_file_path = os.path.join(post_dir, final_file_name)

        while os.path.exists(final_file_path):
            final_file_name = f"{base_name}_{counter}{ext}"
            final_file_path = os.path.join(post_dir, final_file_name)
            counter += 1

        # Копируем файл
        import shutil
        shutil.copy2(file_path, final_file_path)
        logger.info(f"Saved media file to: {final_file_path}")
        return final_file_name

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = (
            "Привет! 👋\n\n"
            "Я бот для сбора идей постов. Используй команду /post для предложения идеи.\n\n"
            "Ты можешь отправить:\n"
            "• Текстовое описание\n"
            "• Фото или видео\n"
            "• Файлы\n"
            "• Пересланные сообщения из других каналов\n\n"
        )
        keyboard = self._create_main_keyboard()
        await update.message.reply_text(welcome_text, reply_markup=keyboard)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий кнопок"""
        query = update.callback_query
        await query.answer()  # Подтверждаем нажатие

        if query.data == 'create_post':
            # Эмулируем команду /post - используем сообщение из callback query
            await query.message.reply_text(
                "Отлично! Теперь пришли мне контент для поста:\n\n"
                "• Текстовое описание идеи\n"
                "• Фото, видео или файлы\n"
                "• Пересланное сообщение из другого канала\n\n",
                reply_markup=self._create_main_keyboard()
            )
            # Устанавливаем состояние ожидания поста
            context.user_data['waiting_for_post'] = True

    async def post_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /post"""
        keyboard = self._create_main_keyboard()
        await update.message.reply_text(
            "Отлично! Теперь пришли мне контент для поста:\n\n"
            "• Текстовое описание идеи\n"
            "• Фото, видео или файлы\n"
            "• Пересланное сообщение из другого канала\n\n",
            reply_markup=keyboard
        )
        # Устанавливаем состояние ожидания поста
        context.user_data['waiting_for_post'] = True

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик всех сообщений"""
        if not context.user_data.get('waiting_for_post'):
            return

        user = update.effective_user
        message = update.message

        # Получаем следующий номер поста
        post_number = self._get_next_post_number()
        post_dir = self._create_post_directory(post_number)

        # Сохраняем текстовый контент
        text_content = []
        if message.text:
            text_content.append(f"Текст сообщения: {message.text}")
        if message.caption:
            text_content.append(f"Подпись: {message.caption}")

        # Обрабатываем пересланные сообщения
        if message.forward_origin:
            if message.forward_origin.type == 'channel':
                text_content.append(f"Переслано из канала: {message.forward_origin.chat.title or 'Неизвестный канал'}")
            elif message.forward_origin.type == 'user':
                text_content.append(f"Переслано от пользователя: {message.forward_origin.sender_user.first_name or 'Неизвестный пользователь'}")

        # Сохраняем информацию о сообщении
        text_content.append(f"Автор поста: {user.first_name} {user.last_name or ''}")
        text_content.append(f"ID пользователя: {user.id}")
        text_content.append(f"Дата создания: {message.date}")

        # Сохраняем текст
        if text_content:
            full_text = "\n".join(text_content)
            self._save_text_content(post_dir, full_text)

        # Обрабатываем медиа файлы
        saved_files = []
        response_text = f"✅ Пост успешно сохранен!\n\n📁 Папка: Пост_{post_number}\n📂 Директория: {post_dir}\n"

        # Фото
        if message.photo:
            photo = message.photo[-1]  # Берем фото в максимальном качестве
            file_size_mb = photo.file_size / (1024 * 1024)

            if file_size_mb > 50:
                logger.warning(f"Фото слишком большое: {file_size_mb:.1f}MB. Пропускаем.")
                response_text += f"\n⚠️ Пропущено фото ({file_size_mb:.1f}MB)"
            else:
                try:
                    file_path = await photo.get_file()
                    await file_path.download_to_drive(f"temp_photo_{user.id}.jpg")
                    saved_name = self._save_media_file(post_dir, f"temp_photo_{user.id}.jpg", "photo.jpg")
                    saved_files.append(saved_name)
                    logger.info(f"Успешно загружено фото ({file_size_mb:.1f}MB)")
                except Exception as e:
                    logger.error(f"Ошибка загрузки фото: {e}")
                    response_text += "\n❌ Ошибка загрузки фото"
                finally:
                    if os.path.exists(f"temp_photo_{user.id}.jpg"):
                        os.remove(f"temp_photo_{user.id}.jpg")

        # Видео
        if message.video:
            video = message.video
            file_size_mb = video.file_size / (1024 * 1024)

            if file_size_mb > 50:
                logger.warning(f"Видео слишком большое: {file_size_mb:.1f}MB. Пропускаем.")
                response_text += f"\n⚠️ Пропущено видео ({file_size_mb:.1f}MB)"
            else:
                try:
                    file_path = await video.get_file()
                    await file_path.download_to_drive(f"temp_video_{user.id}.mp4")
                    saved_name = self._save_media_file(post_dir, f"temp_video_{user.id}.mp4", "video.mp4")
                    saved_files.append(saved_name)
                    logger.info(f"Успешно загружено видео ({file_size_mb:.1f}MB)")
                except Exception as e:
                    logger.error(f"Ошибка загрузки видео: {e}")
                    response_text += "\n❌ Ошибка загрузки видео"
                finally:
                    if os.path.exists(f"temp_video_{user.id}.mp4"):
                        os.remove(f"temp_video_{user.id}.mp4")

        # Документы
        if message.document:
            document = message.document
            file_size_mb = document.file_size / (1024 * 1024)  # Размер в МБ
            temp_filename = None

            try:
                # Проверяем размер файла (Telegram Bot API лимит ~50MB для getFile)
                if file_size_mb > 50:
                    logger.warning(f"Файл слишком большой: {file_size_mb:.1f}MB. Пропускаем.")
                    response_text += f"\n⚠️ Файл '{document.file_name}' слишком большой для загрузки"
                else:
                    file_path = await document.get_file()
                    file_extension = os.path.splitext(document.file_name)[1] or ".bin"
                    temp_filename = f"temp_doc_{user.id}{file_extension}"

                    # Загружаем файл с увеличенным таймаутом
                    await file_path.download_to_drive(temp_filename)
                    saved_name = self._save_media_file(post_dir, temp_filename, document.file_name)
                    saved_files.append(saved_name)
                    logger.info(f"Успешно загружен файл: {document.file_name} ({file_size_mb:.1f}MB)")

            except BadRequest as e:
                if "too big" in str(e).lower():
                    logger.warning(f"Файл слишком большой для загрузки: {document.file_name}")
                    response_text += f"\n⚠️ Файл '{document.file_name}' слишком большой для загрузки"
                else:
                    logger.error(f"Ошибка загрузки файла {document.file_name}: {e}")
                    response_text += f"\n❌ Ошибка загрузки файла '{document.file_name}'"
            except Exception as e:
                logger.error(f"Неожиданная ошибка при загрузке файла {document.file_name}: {e}")
                response_text += f"\n❌ Ошибка загрузки файла '{document.file_name}'"
            finally:
                # Удаляем временный файл
                if temp_filename and os.path.exists(temp_filename):
                    os.remove(temp_filename)

        # Анимации (GIF)
        if message.animation:
            animation = message.animation
            file_size_mb = animation.file_size / (1024 * 1024)

            if file_size_mb > 50:
                logger.warning(f"GIF слишком большой: {file_size_mb:.1f}MB. Пропускаем.")
                response_text += f"\n⚠️ Пропущена GIF ({file_size_mb:.1f}MB)"
            else:
                try:
                    file_path = await animation.get_file()
                    await file_path.download_to_drive(f"temp_animation_{user.id}.gif")
                    saved_name = self._save_media_file(post_dir, f"temp_animation_{user.id}.gif", "animation.gif")
                    saved_files.append(saved_name)
                    logger.info(f"Успешно загружена GIF ({file_size_mb:.1f}MB)")
                except Exception as e:
                    logger.error(f"Ошибка загрузки GIF: {e}")
                    response_text += "\n❌ Ошибка загрузки GIF"
                finally:
                    if os.path.exists(f"temp_animation_{user.id}.gif"):
                        os.remove(f"temp_animation_{user.id}.gif")

        # Аудио
        if message.audio:
            audio = message.audio
            file_size_mb = audio.file_size / (1024 * 1024)

            if file_size_mb > 50:
                logger.warning(f"Аудио слишком большое: {file_size_mb:.1f}MB. Пропускаем.")
                response_text += f"\n⚠️ Пропущено аудио ({file_size_mb:.1f}MB)"
            else:
                try:
                    file_path = await audio.get_file()
                    file_extension = os.path.splitext(audio.file_name)[1] if hasattr(audio, 'file_name') else ".mp3"
                    temp_filename = f"temp_audio_{user.id}{file_extension}"
                    await file_path.download_to_drive(temp_filename)
                    saved_name = self._save_media_file(post_dir, temp_filename, audio.file_name or "audio.mp3")
                    saved_files.append(saved_name)
                    logger.info(f"Успешно загружено аудио ({file_size_mb:.1f}MB)")
                except Exception as e:
                    logger.error(f"Ошибка загрузки аудио: {e}")
                    response_text += "\n❌ Ошибка загрузки аудио"
                finally:
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)

        # Голосовые сообщения
        if message.voice:
            voice = message.voice
            file_size_mb = voice.file_size / (1024 * 1024)

            if file_size_mb > 50:
                logger.warning(f"Голосовое сообщение слишком большое: {file_size_mb:.1f}MB. Пропускаем.")
                response_text += f"\n⚠️ Пропущено голосовое ({file_size_mb:.1f}MB)"
            else:
                try:
                    file_path = await voice.get_file()
                    await file_path.download_to_drive(f"temp_voice_{user.id}.ogg")
                    saved_name = self._save_media_file(post_dir, f"temp_voice_{user.id}.ogg", "voice.ogg")
                    saved_files.append(saved_name)
                    logger.info(f"Успешно загружено голосовое ({file_size_mb:.1f}MB)")
                except Exception as e:
                    logger.error(f"Ошибка загрузки голосового: {e}")
                    response_text += "\n❌ Ошибка загрузки голосового"
                finally:
                    if os.path.exists(f"temp_voice_{user.id}.ogg"):
                        os.remove(f"temp_voice_{user.id}.ogg")

        # Сбрасываем состояние ожидания
        context.user_data['waiting_for_post'] = False

        # Добавляем информацию о контенте в ответ
        if text_content:
            response_text += "\n📝 Сохранен текстовый контент"
        if saved_files:
            response_text += f"\n📎 Сохранено файлов: {len(saved_files)}"

        await update.message.reply_text(response_text)

    def create_application(self):
        """Создание приложения бота"""
        # Создаем приложение с увеличенными таймаутами для больших файлов
        application = (Application.builder()
                      .token(self.token)
                      .get_updates_read_timeout(30)  # Увеличиваем таймаут для получения обновлений
                      .get_updates_write_timeout(30)  # Таймаут для отправки
                      .build())

        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("post", self.post_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(
            filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL |
            filters.ANIMATION | filters.AUDIO | filters.VOICE,
            self.handle_message
        ))

        return application

    async def run_with_retry(self, max_retries=5):
        """Запуск бота с автоматическим перезапуском при конфликтах"""
        application = self.create_application()

        for attempt in range(max_retries):
            try:
                logger.info(f"Попытка запуска бота №{attempt + 1}/{max_retries}")
                logger.info("Bot started successfully!")
                await application.run_polling()
                break  # Если успешно запустился, выходим из цикла

            except Conflict as e:
                if attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)  # Увеличиваем время ожидания
                    logger.warning(f"Конфликт бота (попытка {attempt + 1}). Ожидаем {wait_time} секунд...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Превышено максимальное количество попыток перезапуска")
                    raise e

            except (RetryAfter, TimedOut) as e:
                wait_time = getattr(e, 'retry_after', 60)
                logger.warning(f"Временная ошибка, ждем {wait_time} секунд...")
                await asyncio.sleep(wait_time)

            except BadRequest as e:
                logger.error(f"Ошибка конфигурации бота: {e}")
                break

            except Exception as e:
                logger.error(f"Неожиданная ошибка: {e}")
                if attempt < max_retries - 1:
                    logger.info("Повторная попытка через 30 секунд...")
                    await asyncio.sleep(30)
                else:
                    raise e


# Веб-интерфейс для просмотра логов и постов
class WebInterface:
    def __init__(self, post_bot):
        self.post_bot = post_bot
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/')
        def index():
            html_template = """
            <!DOCTYPE html>
            <html lang="ru">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Telegram Post Bot - Панель управления</title>
                <script src="https://cdn.tailwindcss.com"></script>
            </head>
            <body class="bg-gray-100 min-h-screen">
                <div class="container mx-auto px-4 py-8">
                    <h1 class="text-3xl font-bold text-center mb-8 text-gray-800">
                        📱 Telegram Post Bot - Панель управления
                    </h1>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <!-- Логи -->
                        <div class="bg-white rounded-lg shadow-md p-6">
                            <h2 class="text-xl font-semibold mb-4 text-gray-700">📋 Последние логи</h2>
                            <div class="space-y-2 mb-4" id="logsContainer" style="max-height: 400px; overflow-y: auto;">
                                <div class="text-sm text-gray-600">Загрузка логов...</div>
                            </div>
                            <button onclick="refreshLogs()"
                                class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm">
                                🔄 Обновить логи
                            </button>
                        </div>

                        <!-- Посты -->
                        <div class="bg-white rounded-lg shadow-md p-6">
                            <h2 class="text-xl font-semibold mb-4 text-gray-700">📁 Посты</h2>
                            <div class="space-y-2 mb-4" id="postsContainer" style="max-height: 400px; overflow-y: auto;">
                                <div class="text-sm text-gray-600">Загрузка постов...</div>
                            </div>
                            <button onclick="refreshPosts()"
                                class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded text-sm">
                                🔄 Обновить посты
                            </button>
                        </div>
                    </div>

                    <!-- Детальная информация о посте -->
                    <div class="mt-6 bg-white rounded-lg shadow-md p-6 hidden" id="postDetail">
                        <h2 class="text-xl font-semibold mb-4 text-gray-700">📄 Детали поста</h2>
                        <div id="postContent" class="text-sm text-gray-600">
                            Выберите пост для просмотра деталей
                        </div>
                    </div>
                </div>

                <script>
                    function refreshLogs() {
                        fetch('/api/logs')
                            .then(response => response.json())
                            .then(data => {
                                const container = document.getElementById('logsContainer');
                                container.innerHTML = '';
                                data.logs.forEach(log => {
                                    const div = document.createElement('div');
                                    div.className = 'text-xs p-2 bg-gray-50 rounded border-l-4 ' +
                                        (log.level === 'ERROR' ? 'border-red-500' :
                                         log.level === 'WARNING' ? 'border-yellow-500' : 'border-blue-500');
                                    div.innerHTML = `
                                        <div class="font-mono text-gray-500">${log.time}</div>
                                        <div class="font-semibold text-gray-700">${log.level}</div>
                                        <div class="text-gray-600">${log.message}</div>
                                    `;
                                    container.appendChild(div);
                                });
                            })
                            .catch(error => {
                                console.error('Ошибка загрузки логов:', error);
                                document.getElementById('logsContainer').innerHTML =
                                    '<div class="text-red-500 text-sm">Ошибка загрузки логов</div>';
                            });
                    }

                    function refreshPosts() {
                        fetch('/api/posts')
                            .then(response => response.json())
                            .then(data => {
                                const container = document.getElementById('postsContainer');
                                container.innerHTML = '';
                                data.posts.forEach(post => {
                                    const div = document.createElement('div');
                                    div.className = 'text-sm p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100';
                                    div.onclick = () => showPostDetail(post.name);
                                    div.innerHTML = `
                                        <div class="font-semibold text-gray-700">${post.name}</div>
                                        <div class="text-gray-500">${post.created}</div>
                                        <div class="text-gray-600">${post.files_count} файлов</div>
                                    `;
                                    container.appendChild(div);
                                });
                            })
                            .catch(error => {
                                console.error('Ошибка загрузки постов:', error);
                                document.getElementById('postsContainer').innerHTML =
                                    '<div class="text-red-500 text-sm">Ошибка загрузки постов</div>';
                            });
                    }

                    function showPostDetail(postName) {
                        fetch(`/api/posts/${postName}`)
                            .then(response => response.json())
                            .then(data => {
                                const detailDiv = document.getElementById('postDetail');
                                const contentDiv = document.getElementById('postContent');

                                detailDiv.classList.remove('hidden');
                                contentDiv.innerHTML = `
                                    <div class="mb-4">
                                        <h3 class="font-semibold text-lg">${data.name}</h3>
                                        <p class="text-gray-500">Создано: ${data.created}</p>
                                    </div>
                                    <div class="mb-4">
                                        <h4 class="font-semibold">Содержимое:</h4>
                                        <pre class="bg-gray-50 p-3 rounded text-xs overflow-x-auto">${data.content}</pre>
                                    </div>
                                    ${data.files.length > 0 ? `
                                    <div>
                                        <h4 class="font-semibold">Файлы:</h4>
                                        <ul class="list-disc list-inside">
                                            ${data.files.map(file => `<li>${file}</li>`).join('')}
                                        </ul>
                                    </div>
                                    ` : ''}
                                `;
                            })
                            .catch(error => {
                                console.error('Ошибка загрузки деталей поста:', error);
                                document.getElementById('postContent').innerHTML =
                                    '<div class="text-red-500 text-sm">Ошибка загрузки деталей поста</div>';
                            });
                    }

                    // Автообновление каждые 30 секунд
                    setInterval(() => {
                        refreshLogs();
                        refreshPosts();
                    }, 30000);

                    // Первоначальная загрузка
                    refreshLogs();
                    refreshPosts();
                </script>
            </body>
            </html>
            """
            return render_template_string(html_template)

        @self.app.route('/api/logs')
        def get_logs():
            try:
                logs = []
                if os.path.exists('bot.log'):
                    with open('bot.log', 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # Берем последние 50 строк
                        for line in lines[-50:]:
                            parts = line.strip().split(' - ')
                            if len(parts) >= 4:
                                time_part = parts[0] + ' ' + parts[1]
                                level = parts[2]
                                message = ' - '.join(parts[3:])
                                logs.append({
                                    'time': time_part,
                                    'level': level,
                                    'message': message
                                })
                return jsonify({'logs': logs})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/posts')
        def get_posts():
            try:
                posts = []
                if os.path.exists(self.post_bot.posts_dir):
                    for item in os.listdir(self.post_bot.posts_dir):
                        post_path = os.path.join(self.post_bot.posts_dir, item)
                        if os.path.isdir(post_path) and item.startswith('Пост_'):
                            created_time = datetime.fromtimestamp(os.path.getctime(post_path))
                            files = [f for f in os.listdir(post_path) if os.path.isfile(os.path.join(post_path, f))]
                            posts.append({
                                'name': item,
                                'created': created_time.strftime('%Y-%m-%d %H:%M:%S'),
                                'files_count': len(files)
                            })
                # Сортируем по времени создания (новые первыми)
                posts.sort(key=lambda x: x['created'], reverse=True)
                return jsonify({'posts': posts})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/posts/<post_name>')
        def get_post_detail(post_name):
            try:
                post_path = os.path.join(self.post_bot.posts_dir, post_name)
                if not os.path.exists(post_path):
                    return jsonify({'error': 'Пост не найден'}), 404

                content = ''
                content_file = os.path.join(post_path, 'content.txt')
                if os.path.exists(content_file):
                    with open(content_file, 'r', encoding='utf-8') as f:
                        content = f.read()

                files = [f for f in os.listdir(post_path) if os.path.isfile(os.path.join(post_path, f))]
                created_time = datetime.fromtimestamp(os.path.getctime(post_path))

                return jsonify({
                    'name': post_name,
                    'created': created_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'content': content,
                    'files': files
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    def run_web_server(self, host='0.0.0.0', port=None):
        """Запуск веб-сервера в отдельном потоке"""
        if port is None:
            port = int(os.environ.get('PORT', 8080))
        self.app.run(host=host, port=port, debug=False)


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"Получен сигнал {signum}, завершение работы...")
    shutdown_event.set()
    if bot_instance:
        logger.info("Остановка бота...")
        # Здесь можно добавить логику остановки бота
    sys.exit(0)

# Регистрируем обработчики сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Основная функция запуска бота"""
    global bot_instance
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.info("Please create a .env file with your bot token:")
        logger.info("TELEGRAM_BOT_TOKEN=your_bot_token_here")
        return

    bot = PostBot(token)
    bot_instance = bot

    # Создаем веб-интерфейс
    web_interface = WebInterface(bot)

    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(
        target=web_interface.run_web_server,
        daemon=True
    )
    web_thread.start()

    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🌐 Веб-интерфейс запущен на http://0.0.0.0:{port}")
    logger.info("📱 Telegram бот запускается...")

    while not shutdown_event.is_set():
        try:
            logger.info("🚀 Запуск Telegram бота в фоновом режиме...")
            await bot.run_with_retry(max_retries=10)
            break  # Если успешно запустился и работал, выходим

        except KeyboardInterrupt:
            logger.info("⏹️  Бот остановлен пользователем")
            break

        except Exception as e:
            logger.error(f"❌ Критическая ошибка бота: {e}")
            if shutdown_event.is_set():
                break
            logger.info("🔄 Перезапуск через 60 секунд...")
            await asyncio.sleep(60)
    
    logger.info("🛑 Бот завершает работу...")

if __name__ == '__main__':
    # With nest_asyncio applied, we can use asyncio.run() normally
    asyncio.run(main())