import logging
import sqlite3
import json
from datetime import datetime, timedelta
import random # Для выбора случайного элемента из кейса

from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext # Хотя для текущего функционала пока не используется, может пригодиться
from aiogram.fsm.state import State, StatesGroup # Аналогично

# --- НАСТРОЙКИ БОТА ---
# ВАШ ТОКЕН БОТА, полученный от BotFather
TOKEN = '7710323220:AAETXXUvqNReRywbPzJUgwybs0tBAGGZZ44Ь' 

# ID пользователя Telegram, который будет получать уведомления (это ваш числовой ID)
# Чтобы узнать свой ID, запустите этого бота и отправьте ему команду /myid
MANAGER_CHAT_ID = 1101669771 # ЗАМЕНИТЕ НА ВАШ ЧИСЛОВОЙ ID МЕНЕДЖЕРА

# URL вашего Telegram Mini App (Web App) на GitHub Pages
# Убедитесь, что это правильная ссылка, указывающая на index.html
MINI_APP_URL = 'https://lehakaraba.github.io/my-telegram-webapp-test/'

# --- КОНФИГУРАЦИЯ ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ИНИЦИАЛИЗАЦИЯ AIOGRAM ---
bot = Bot(token=TOKEN)
storage = MemoryStorage() # Используем MemoryStorage для простоты, для продакшена лучше Redis
dp = Dispatcher(storage=storage)

# --- СТРУКТУРА ДАННЫХ ДЛЯ КЕЙСОВ ---
# Здесь определяется содержимое каждого кейса, его стоимость,
# описание, изображение и список возможных предметов с их весами (шансами).
# Вес (weight) - это относительная "тяжесть" выпадения предмета.
# Чем больше вес, тем выше шанс.
# Для звезд: "value" - количество звезд. Для предметов/NFT: "value" - уникальный ID/название предмета.
CASES_DATA = {
    "free_case": {
        "name": "Бесплатный Кейс",
        "cost": 0,
        "description": "Крути раз в день бесплатно! Выигрывай звезды и редкие предметы.",
        "image": "D:\Games\TgStarsCase\images\free_case.png", # Укажите реальный путь к изображению кейса
        "items": [
            {"name": "25 ⭐", "value": 25, "weight": 70},
            {"name": "50 ⭐", "value": 50, "weight": 30},
            {"name": "100 ⭐", "value": 100, "weight": 0},
            {"name": "Подарочная роза", "value": "red_rose", "weight": 7},
            {"name": "Коробка с подарком", "value": "gift_box", "weight": 3},
        ]
    },
    "premium_case_1000": {
        "name": "Премиум NFT Кейс",
        "cost": 1000,
        "description": "Получи эксклюзивные NFT-активы! Все предметы - уникальные NFT.",
        "image": "https://lehakaraba.github.io/my-telegram-webapp/images/nft_case.png", # Укажите реальный путь к изображению NFT кейса
        "items": [
            {"name": "NFT: Кристальный Меч", "value": "nft_crystal_sword", "weight": 50},
            {"name": "NFT: Древний Щит", "value": "nft_ancient_shield", "weight": 30},
            {"name": "NFT: Мистический Артефакт", "value": "nft_mystic_artifact", "weight": 15},
            {"name": "NFT: Легендарный Дракон", "value": "nft_legendary_dragon", "weight": 5},
        ]
    },
    # Добавляйте другие кейсы по мере необходимости
    # "another_case": {
    #     "name": "Другой Кейс",
    #     "cost": 500,
    #     "description": "Описание другого кейса.",
    #     "image": "https://lehakaraba.github.io/my-telegram-webapp/images/another_case.png",
    #     "items": [
    #         {"name": "Предмет 1", "value": "item_one", "weight": 70},
    #         {"name": "Предмет 2", "value": "item_two", "weight": 30},
    #     ]
    # }
}

# --- ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ (users.db) ---
# База данных будет хранить:
# - user_id, username, stars
# - last_daily_bonus (для звезд)
# - last_free_case_opened (для бесплатного кейса)
# - Инвентарь пользователя (item_name, quantity)

DATABASE_NAME = 'users.db'

def get_db_connection():
    """Устанавливает соединение с базой данных."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row # Позволяет получать строки как объекты-словари
    return conn

def init_db():
    """Инициализирует структуру базы данных (создает таблицы, если их нет)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица для пользователей и их основных данных
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            stars INTEGER DEFAULT 0,
            last_daily_bonus TEXT DEFAULT '1970-01-01 00:00:00', -- Дата последнего получения ежедневного бонуса
            last_free_case_opened TEXT DEFAULT '1970-01-01 00:00:00' -- Дата последнего открытия бесплатного кейса
        )
    ''')

    # Таблица для инвентаря пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            item_name TEXT,
            quantity INTEGER DEFAULT 1,
            PRIMARY KEY (user_id, item_name), -- Составной ключ
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована.")

def get_or_create_user(user_id: int, username: str) -> dict:
    """Получает данные пользователя из БД или создает новую запись."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            'INSERT INTO users (user_id, username, stars, last_daily_bonus, last_free_case_opened) VALUES (?, ?, ?, ?, ?)',
            (user_id, username, 0, '1970-01-01 00:00:00', '1970-01-01 00:00:00')
        )
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        logger.info(f"Новый пользователь создан: {username} (ID: {user_id})")
    conn.close()
    return dict(user) # Возвращаем как словарь для удобства

def update_stars(user_id: int, amount: int) -> int:
    """Обновляет количество звезд пользователя. Возвращает новое количество звезд."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET stars = stars + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
    new_stars = cursor.fetchone()['stars']
    conn.close()
    logger.info(f"Звезды пользователя {user_id} обновлены на {amount}. Текущий баланс: {new_stars}")
    return new_stars

def get_stars(user_id: int) -> int:
    """Возвращает текущее количество звезд пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT stars FROM users WHERE user_id = ?', (user_id,))
    stars = cursor.fetchone()['stars']
    conn.close()
    return stars

def add_or_update_inventory_item(user_id: int, item_name: str, quantity: int = 1):
    """Добавляет или обновляет предмет в инвентаре пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT quantity FROM inventory WHERE user_id = ? AND item_name = ?', (user_id, item_name))
    existing_item = cursor.fetchone()

    if existing_item:
        new_quantity = existing_item['quantity'] + quantity
        cursor.execute('UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_name = ?', (new_quantity, user_id, item_name))
        logger.info(f"Обновлен инвентарь пользователя {user_id}: предмет '{item_name}' теперь {new_quantity} шт.")
    else:
        cursor.execute('INSERT INTO inventory (user_id, item_name, quantity) VALUES (?, ?, ?)', (user_id, item_name, quantity))
        logger.info(f"Добавлен предмет в инвентарь пользователя {user_id}: '{item_name}' ({quantity} шт.)")
    conn.commit()
    conn.close()

def get_user_inventory(user_id: int) -> list:
    """Возвращает список предметов в инвентаре пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT item_name, quantity FROM inventory WHERE user_id = ?', (user_id,))
    inventory = cursor.fetchall()
    conn.close()
    return [dict(row) for row in inventory]

def check_and_give_daily_bonus(user_id: int) -> tuple[bool, int]:
    """Проверяет и выдает ежедневный бонус (звезды), если прошел 1 день."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT last_daily_bonus FROM users WHERE user_id = ?', (user_id,))
    last_bonus_str = cursor.fetchone()['last_daily_bonus']
    last_bonus_time = datetime.strptime(last_bonus_str, '%Y-%m-%d %H:%M:%S')

    now = datetime.now()
    if now - last_bonus_time >= timedelta(days=1):
        bonus_amount = 100 # Размер ежедневного бонуса
        update_stars(user_id, bonus_amount)
        cursor.execute('UPDATE users SET last_daily_bonus = ? WHERE user_id = ?', (now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} получил ежедневный бонус: {bonus_amount} звезд.")
        return True, bonus_amount
    conn.close()
    logger.info(f"Пользователь {user_id} уже получал ежедневный бонус сегодня.")
    return False, 0

def check_and_mark_free_case_opened(user_id: int) -> bool:
    """Проверяет возможность открыть бесплатный кейс и отмечает его открытие."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT last_free_case_opened FROM users WHERE user_id = ?', (user_id,))
    last_opened_str = cursor.fetchone()['last_free_case_opened']
    last_opened_time = datetime.strptime(last_opened_str, '%Y-%m-%d %H:%M:%S')

    now = datetime.now()
    if now - last_opened_time >= timedelta(days=1):
        cursor.execute('UPDATE users SET last_free_case_opened = ? WHERE user_id = ?', (now.strftime('%Y-%m-%d %H:%M:%S'), user_id))
        conn.commit()
        conn.close()
        logger.info(f"Пользователь {user_id} открыл бесплатный кейс.")
        return True
    conn.close()
    logger.info(f"Пользователь {user_id} уже открывал бесплатный кейс сегодня.")
    return False

def choose_item_from_case(case_id: str) -> dict:
    """Выбирает случайный предмет из кейса на основе весов."""
    case_info = CASES_DATA.get(case_id)
    if not case_info or not case_info['items']:
        logger.error(f"Попытка выбрать предмет из неизвестного или пустого кейса: {case_id}")
        return None

    items = case_info['items']
    total_weight = sum(item['weight'] for item in items)
    if total_weight == 0:
        logger.warning(f"Суммарный вес предметов в кейсе {case_id} равен 0. Выбор невозможен.")
        return None

    random_point = random.uniform(0, total_weight)
    current_weight = 0
    for item in items:
        current_weight += item['weight']
        if random_point <= current_weight:
            return item
    return None # На случай, если что-то пойдет не так (крайне маловероятно)

# --- ФУНКЦИИ УВЕДОМЛЕНИЙ ---
async def send_manager_notification(message_text: str):
    """Отправляет уведомление менеджеру."""
    if MANAGER_CHAT_ID == 000000000:
        logger.warning("MANAGER_CHAT_ID не установлен. Уведомление не отправлено.")
        return
    try:
        await bot.send_message(MANAGER_CHAT_ID, message_text)
        logger.info(f"Уведомление менеджеру ({MANAGER_CHAT_ID}): {message_text}")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление менеджеру: {e}", exc_info=True)

# --- ОБРАБОТЧИКИ СООБЩЕНИЙ И КОЛБЭКОВ ---

@dp.message(lambda message: message.text == '/start')
async def handle_start(message: types.Message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else f"id_{user_id}"
    user = get_or_create_user(user_id, username)

    # Создаем кнопки для главного меню
    markup = InlineKeyboardMarkup(inline_keyboard=[])

    # Кнопка для открытия Web App (основной экран игры)
    # Пока не передаем specific_case_id, Web App будет сам решать, что отображать
    markup.add(InlineKeyboardButton(text="🕹️ Открыть игру", web_app=WebAppInfo(url=MINI_APP_URL)))

    # Кнопки для выбора кейсов
    case_buttons_row = []
    for case_id, case_info in CASES_DATA.items():
        case_buttons_row.append(
            InlineKeyboardButton(
                text=f"{case_info['name']} ({case_info['cost']} ⭐)",
                callback_data=f"show_case_menu_{case_id}"
            )
        )
    markup.add(*case_buttons_row) # Добавляем кнопки кейсов в один ряд

    # Кнопка ежедневного бонуса
    markup.add(InlineKeyboardButton(text="💰 Ежедневный бонус", callback_data="get_daily_bonus"))
    
    # Кнопка "Мой инвентарь"
    markup.add(InlineKeyboardButton(text="📦 Мой инвентарь", callback_data="show_inventory"))

    await message.answer(
        f"Привет, {message.from_user.full_name}! 👋\n"
        f"Добро пожаловать в игру! Твои звезды: {user['stars']} ⭐",
        reply_markup=markup
    )
    logger.info(f"Пользователь {user_id} вызвал /start. Звезд: {user['stars']}")

@dp.callback_query(lambda c: c.data == 'back_to_main_menu')
async def back_to_main_menu_handler(callback_query: types.CallbackQuery):
    """Обработчик для кнопки 'Назад в меню'."""
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username if callback_query.from_user.username else f"id_{user_id}"
    user = get_or_create_user(user_id, username)

    markup = InlineKeyboardMarkup(inline_keyboard=[])
    markup.add(InlineKeyboardButton(text="🕹️ Открыть игру", web_app=WebAppInfo(url=MINI_APP_URL)))
    
    case_buttons_row = []
    for case_id, case_info in CASES_DATA.items():
        case_buttons_row.append(
            InlineKeyboardButton(
                text=f"{case_info['name']} ({case_info['cost']} ⭐)",
                callback_data=f"show_case_menu_{case_id}"
            )
        )
    markup.add(*case_buttons_row)

    markup.add(InlineKeyboardButton(text="💰 Ежедневный бонус", callback_data="get_daily_bonus"))
    markup.add(InlineKeyboardButton(text="📦 Мой инвентарь", callback_data="show_inventory"))


    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"Привет, {callback_query.from_user.full_name}! 👋\n"
             f"Добро пожаловать в игру! Твои звезды: {user['stars']} ⭐",
        reply_markup=markup
    )
    await callback_query.answer()
    logger.info(f"Пользователь {user_id} вернулся в главное меню.")

@dp.callback_query(lambda c: c.data == 'get_daily_bonus')
async def handle_daily_bonus(callback_query: types.CallbackQuery):
    """Обработчик для получения ежедневного бонуса."""
    user_id = callback_query.from_user.id
    success, bonus_amount = check_and_give_daily_bonus(user_id)

    if success:
        await callback_query.answer(f"Ты получил {bonus_amount} ⭐ за ежедневный бонус!", show_alert=True)
    else:
        await callback_query.answer("Ты уже получал сегодня бонус. Приходи завтра!", show_alert=True)
    
    # Обновляем сообщение, чтобы показать актуальное количество звезд
    await back_to_main_menu_handler(callback_query) # Переиспользуем функцию для обновления главного меню

@dp.callback_query(lambda c: c.data.startswith('show_case_menu_'))
async def handle_show_case_menu(callback_query: types.CallbackQuery):
    """Обработчик для показа детального меню выбранного кейса."""
    case_id = callback_query.data.replace('show_case_menu_', '')
    case_info = CASES_DATA.get(case_id)
    user_id = callback_query.from_user.id
    user = get_or_create_user(user_id, callback_query.from_user.username or f"id_{user_id}")

    if not case_info:
        await callback_query.answer("Кейс не найден.", show_alert=True)
        logger.warning(f"Пользователь {user_id} запросил несуществующий кейс: {case_id}")
        return

    text = (
        f"**{case_info['name']}**\n"
        f"Стоимость: {case_info['cost']} ⭐\n"
        f"Твои звезды: {user['stars']} ⭐\n\n"
        f"{case_info['description']}\n\n"
        f"**Вы можете выиграть:**\n"
    )

    total_weight = sum(item['weight'] for item in case_info['items'])
    if total_weight == 0 and case_info['items']: # Если предметы есть, но вес 0
        text += "Нет предметов с весом для расчета шанса.\n"
    else:
        for item in case_info['items']:
            percentage = (item['weight'] / total_weight * 100) if total_weight > 0 else 0
            # Если это звезды, показываем звезды, иначе название предмета
            display_name = f"{item['value']} ⭐" if isinstance(item['value'], int) else item['name']
            text += f"- {display_name} ({percentage:.2f}%)\n"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Крутить!", callback_data=f"open_case_in_app_{case_id}")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main_menu")]
    ])

    # Отправляем фото кейса, если оно есть, иначе редактируем сообщение
    if case_info.get('image'):
        try:
            await bot.send_photo(
                chat_id=callback_query.message.chat.id,
                photo=case_info['image'],
                caption=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            # Удаляем старое сообщение, если оно не было фото (чтобы избежать дублирования)
            if callback_query.message.photo is None:
                await callback_query.message.delete()
        except Exception as e:
            logger.error(f"Не удалось отправить фото кейса {case_id}: {e}", exc_info=True)
            # В случае ошибки отправки фото, отправляем текст
            await bot.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text=text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
    else:
        await bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    await callback_query.answer()
    logger.info(f"Пользователь {user_id} просматривает кейс: {case_id}")


@dp.callback_query(lambda c: c.data.startswith('open_case_in_app_'))
async def handle_open_case_in_app(callback_query: types.CallbackQuery):
    """Обработчик для запуска Web App для кручения кейса."""
    user_id = callback_query.from_user.id
    case_id = callback_query.data.replace('open_case_in_app_', '')
    case_info = CASES_DATA.get(case_id)
    user = get_or_create_user(user_id, callback_query.from_user.username or f"id_{user_id}")

    if not case_info:
        await callback_query.answer("Кейс не найден.", show_alert=True)
        return

    # Проверка условий открытия кейса
    if case_id == "free_case":
        if not check_and_mark_free_case_opened(user_id):
            await callback_query.answer("Бесплатный кейс можно открыть только раз в день. Приходи завтра!", show_alert=True)
            return
        logger.info(f"Пользователь {user_id} открывает бесплатный кейс.")
    else:
        # Для платных кейсов
        if user['stars'] < case_info['cost']:
            await callback_query.answer(f"Недостаточно звезд для открытия этого кейса. Нужно {case_info['cost']} ⭐. Твои звезды: {user['stars']} ⭐", show_alert=True)
            return
        
        # Списываем звезды
        update_stars(user_id, -case_info['cost'])
        logger.info(f"Пользователь {user_id} списал {case_info['cost']} звезд за кейс {case_id}. Остаток: {get_stars(user_id)}")
        await callback_query.answer(f"Списано {case_info['cost']} ⭐. Запускаю открытие кейса!", show_alert=True)
    
    # Готовим данные для передачи в Web App
    # Используем json.dumps для преобразования списка словарей в строку JSON
    # Это позволяет Web App получить полную информацию о предметах и их шансах
    web_app_params = {
        "case_id": case_id,
        "case_name": case_info['name'],
        "case_cost": case_info['cost'],
        "items": case_info['items'],
        "user_stars": get_stars(user_id) # Передаем актуальное количество звезд
    }
    
    # Кодируем параметры в URL для Web App
    # Это не оптимальный способ для больших данных, но для начала сойдет.
    # Более надежный способ: использовать Telegram.WebApp.initDataUnsafe или запрос из Web App.
    encoded_params = json.dumps(web_app_params)
    
    # URL для Web App с закодированными параметрами.
    # Web App должен будет распарсить эти параметры из window.location.search
    final_web_app_url = f"{MINI_APP_URL}?data={encoded_params}"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Открыть в игре", web_app=WebAppInfo(url=final_web_app_url))],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main_menu")]
    ])

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"Выбран кейс **«{case_info['name']}»**.\nНажмите кнопку ниже, чтобы запустить Web App и открыть его!",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await callback_query.answer()
    logger.info(f"Пользователь {user_id} запускает Web App для кейса: {case_id}")


@dp.callback_query(lambda c: c.data == 'show_inventory')
async def handle_show_inventory(callback_query: types.CallbackQuery):
    """Обработчик для показа инвентаря пользователя."""
    user_id = callback_query.from_user.id
    inventory = get_user_inventory(user_id)

    text = "**Твой инвентарь:**\n\n"
    if not inventory:
        text += "Инвентарь пуст."
    else:
        for item in inventory:
            text += f"- {item['item_name']} (x{item['quantity']})\n"
            # Здесь можно добавить кнопку "Вывести" для каждого предмета,
            # но это усложнит Inline Keyboard. Лучше делать вывод через Web App.
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_main_menu")]
    ])
    # Если хотим показывать инвентарь в Web App, то можно так:
    # markup.add(InlineKeyboardButton(text="Открыть инвентарь в Web App", web_app=WebAppInfo(url="ВАШ_URL_ИНВЕНТАРЯ_В_WEBAPP")))

    await bot.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await callback_query.answer()
    logger.info(f"Пользователь {user_id} просматривает инвентарь.")


@dp.message(lambda message: message.web_app_data)
async def web_app_data_handler(message: types.Message):
    """Обработчик данных, приходящих из Telegram Mini App."""
    user_id = message.from_user.id
    data_from_webapp = message.web_app_data.data # Это строка JSON из Web App
    logger.info(f"Получены данные из Web App от пользователя {user_id}: {data_from_webapp}")

    try:
        parsed_data = json.loads(data_from_webapp)
        action = parsed_data.get('action')

        if action == 'case_opened_result':
            # Web App сообщает, какой предмет был выигран в кейсе
            case_id = parsed_data.get('case_id')
            item_value = parsed_data.get('item_value') # Может быть числом (звезды) или строкой (предмет/NFT)
            item_name = parsed_data.get('item_name') # Отображаемое имя предмета
            
            # Логика выдачи предмета/звезд
            if isinstance(item_value, int): # Если это звезды
                update_stars(user_id, item_value)
                await message.answer(f"🎉 Поздравляем! Вы выиграли {item_value} ⭐!", reply_markup=types.ReplyKeyboardRemove())
                logger.info(f"Пользователь {user_id} выиграл {item_value} звезд из кейса {case_id}")
            elif isinstance(item_value, str): # Если это предмет/NFT
                add_or_update_inventory_item(user_id, item_name) # Используем item_name для инвентаря
                await message.answer(f"🎁 Поздравляем! Вы выиграли предмет: **{item_name}**!", reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")
                logger.info(f"Пользователь {user_id} выиграл предмет '{item_name}' из кейса {case_id}")
            else:
                await message.answer("Ошибка: Неизвестный тип результата кейса.")
                logger.error(f"Неизвестный тип item_value из Web App: {item_value}")

        elif action == 'request_item_withdrawal':
            # Запрос на вывод предмета
            item_name = parsed_data.get('item_name')
            quantity = parsed_data.get('quantity', 1)
            
            # Здесь можно добавить логику проверки наличия предмета в инвентаре
            # Например: if item_in_inventory(user_id, item_name, quantity):
            
            await send_manager_notification(
                f"🚨 НОВЫЙ ЗАПРОС НА ВЫВОД ПРЕДМЕТА!\n"
                f"Пользователь: @{message.from_user.username} (ID: `{user_id}`)\n"
                f"Предмет: **{item_name}** (x{quantity} шт.)\n"
                f"Для связи с пользователем: t.me/{message.from_user.username}"
            )
            await message.answer(f"✅ Твой запрос на вывод предмета '{item_name}' отправлен менеджеру. Ожидай, когда с тобой свяжутся.")
            logger.info(f"Пользователь {user_id} запросил вывод '{item_name}' (x{quantity})")
        
        elif action == 'update_user_stars_from_webapp':
            # Пример, если Web App сам управляет звездами и сообщает боту об изменении
            amount = parsed_data.get('amount')
            if amount is not None and isinstance(amount, int):
                new_stars = update_stars(user_id, amount)
                # Можно отправить ответ обратно в Web App, если нужно
                # Telegram.WebApp.sendData(json.dumps({'action': 'stars_updated', 'new_stars': new_stars}))
                await message.answer(f"Твои звезды обновлены. Текущий баланс: {new_stars} ⭐")
                logger.info(f"Звезды пользователя {user_id} обновлены Web App. Текущий баланс: {new_stars}")
            else:
                await message.answer("Ошибка при обновлении звезд из Web App: неверная сумма.")

        # Здесь можно добавить другие действия из Web App, например, 'buy_upgrade', 'send_feedback' и т.д.
        else:
            await message.answer("Неизвестное действие из Web App.")
            logger.warning(f"Получено неизвестное действие из Web App: {action}")

    except json.JSONDecodeError:
        await message.answer("Ошибка: Неверный формат данных из Web App (ожидался JSON).")
        logger.error(f"Ошибка JSON при парсинге данных из Web App: {data_from_webapp}", exc_info=True)
    except Exception as e:
        await message.answer(f"Произошла ошибка при обработке данных Web App: {e}")
        logger.error(f"Непредвиденная ошибка при обработке данных Web App: {e}", exc_info=True)

@dp.message(lambda message: message.text == '/myid')
async def send_my_id(message: types.Message):
    """Отправляет пользователю его ID."""
    await message.answer(f"Твой ID пользователя: `{message.from_user.id}`\n"
                         f"Имя пользователя: `{message.from_user.username if message.from_user.username else 'нет'}`",
                         parse_mode="Markdown")
    logger.info(f"Пользователь {message.from_user.id} запросил свой ID.")

# --- ЗАПУСК БОТА ---
async def main():
    """Главная функция для запуска бота."""
    init_db() # Инициализируем БД при каждом запуске (создает, если нет)
    logger.info("Бот запущен и готов принимать команды!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    # Запускаем асинхронную функцию main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)