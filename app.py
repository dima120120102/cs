import os
import json
import logging
import gevent
from gevent import monkey

# Применяем патч для асинхронных операций
monkey.patch_all()

from urllib.parse import urlencode, parse_qs, urlparse
from flask import Flask, redirect, request, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO
from supabase import create_client, Client
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")
CORS(app, resources={r"/api/*": {"origins": "https://cq34195.tw1.ru"}})

# Supabase конфигурация
SUPABASE_URL = "https://gxeviitquermnukavhvj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4ZXZpaXRxdWVybW51a2F2aHZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI4MjY5NjgsImV4cCI6MjA1ODQwMjk2OH0.FOZnKiCzhL1UPVzOttN4RhFtrkplamHho6flpibdCx8"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("Supabase клиент успешно инициализирован")
except Exception as e:
    logging.error(f"Ошибка инициализации Supabase клиента: {str(e)}")
    raise

# YooMoney конфигурация
YOOMONEY_TOKEN = "4100118955444810.E95E06426A066F86D534109D8F3D266DCEE11732C5D01ECCF7F23D414A40CA86E76B4371ACDCAC7BC51078846C253CDC240F0A949335D0E6B5DED77C01D9FD1044302C7C61211F76B41ED8C5CF861F70C6527621082C007E7E4DB84F5A2A5A0C1EF25CD6780B6519F5DAEEA8B3B6CC6D31B72282A6272C077D81774E599FC67D"
YOOMONEY_CLIENT_ID = "5D57E13F8ADEBA157A38E3D584C557026397D65F5D0A8CB67F74894240C8AC76"
YOOMONEY_REDIRECT_URI = "https://cs2cases.onrender.com/yoomoney/callback"
YOOMONEY_API_URL = "https://api.yoomoney.ru/v1/operation-history"

# Функция обработки доната
def process_donation(steam_id, amount):
    user = supabase.table('users').select('balance').eq('steam_id', steam_id).execute()
    if user.data:
        new_balance = user.data[0]['balance'] + amount
        supabase.table('users').update({'balance': new_balance}).eq('steam_id', steam_id).execute()
        socketio.emit('balance_update', {'steam_id': steam_id, 'balance': new_balance})
        logging.info(f"Баланс обновлен: {steam_id} -> {new_balance}")
    else:
        logging.warning(f"Пользователь не найден: {steam_id}")

# Периодическая проверка через API
def init_yoomoney_integration():
    def check_transactions():
        if not YOOMONEY_TOKEN:
            logging.error("YOOMONEY_TOKEN не установлен, пропускаем проверку")
            return
        last_operation_id = None
        while True:
            try:
                headers = {"Authorization": f"Bearer {YOOMONEY_TOKEN}"}
                params = {"records": 10, "type": "deposition"}
                response = requests.post(YOOMONEY_API_URL, headers=headers, params=params)
                response.raise_for_status()
                operations = response.json().get('operations', [])

                for operation in operations:
                    operation_id = operation.get('operation_id')
                    if last_operation_id and operation_id == last_operation_id:
                        continue
                    steam_id = operation.get('message', '').strip()
                    if not steam_id:
                        logging.warning("SteamID не указан в комментарии")
                        continue
                    amount = float(operation.get('amount', 0))
                    process_donation(steam_id, amount)
                    last_operation_id = operation_id
            except Exception as e:
                logging.error(f"Ошибка при проверке YooMoney: {str(e)}")
            gevent.sleep(60)

    socketio.start_background_task(check_transactions)

# Webhook от YooMoney
@app.route('/yoomoney/webhook', methods=['POST'])
def yoomoney_webhook():
    try:
        data = request.json
        if not data:
            logging.error("Webhook: Нет данных")
            return "No data", 400
        if data.get('notification_type') != 'p2p-incoming':
            return "Not a donation", 200
        steam_id = data.get('label', '').strip()
        if not steam_id:
            logging.warning("Webhook: SteamID не указан")
            return "No SteamID", 200
        amount = float(data.get('amount', 0))
        process_donation(steam_id, amount)
        return "OK", 200
    except Exception as e:
        logging.error(f"Ошибка в Webhook: {str(e)}")
        return "Error", 500

# OAuth2 авторизация
@app.route('/yoomoney/auth')
def yoomoney_auth():
    auth_url = "https://yoomoney.ru/oauth/authorize"
    params = {
        "client_id": YOOMONEY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": YOOMONEY_REDIRECT_URI,
        "scope": "account-info operation-history"
    }
    redirect_url = f"{auth_url}?{urlencode(params)}"
    return redirect(redirect_url)

# Обработка Redirect URI
@app.route('/yoomoney/callback')
def yoomoney_callback():
    try:
        code = request.args.get('code')
        if not code:
            logging.error("OAuth2: Код авторизации не получен")
            return "No authorization code", 400

        token_url = "https://yoomoney.ru/oauth/token"
        payload = {
            "code": code,
            "client_id": YOOMONEY_CLIENT_ID,
            "grant_type": "authorization_code",
            "redirect_uri": YOOMONEY_REDIRECT_URI
        }
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")

        if access_token:
            global YOOMONEY_TOKEN
            YOOMONEY_TOKEN = access_token
            logging.info(f"OAuth2: Токен успешно получен: {access_token}")
            return "Токен получен! Можете закрыть эту страницу."
        else:
            logging.error("OAuth2: Не удалось получить токен")
            return "Ошибка получения токена", 400
    except Exception as e:
        logging.error(f"Ошибка в OAuth2 callback: {str(e)}")
        return f"Ошибка: {str(e)}", 500

@app.route('/test')
def test():
    logging.info("Маршрут /test вызван")
    return "Сервер работает!"

# Остальные маршруты остаются без изменений
@app.route('/login')
def login():
    try:
        steam_login_url = 'https://steamcommunity.com/openid/login'
        params = {
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.mode': 'checkid_setup',
            'openid.return_to': 'https://cs2cases.onrender.com/auth',
            'openid.realm': 'https://cs2cases.onrender.com',
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
            'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
        }
        redirect_url = f"{steam_login_url}?{urlencode(params)}"
        logging.info(f"Redirect URI: {redirect_url}")
        return redirect(redirect_url)
    except Exception as e:
        logging.error(f"Ошибка в /login: {str(e)}")
        return f"Ошибка: {str(e)}", 500

@app.route('/auth')
def auth():
    try:
        query = urlparse(request.url).query
        params = parse_qs(query)
        params['openid.mode'] = 'check_authentication'
        
        response = requests.get('https://steamcommunity.com/openid/login', params=params)
        logging.info(f"Ответ от Steam: {response.text}")
        
        if 'is_valid:true' in response.text:
            steam_id = params['openid.claimed_id'][0].split('/')[-1]
            user_name = f"User_{steam_id[-4:]}"
            logging.info(f"Авторизация успешна, Steam ID: {steam_id}")
            
            response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
            if not response.data:
                supabase.table('users').insert({
                    'steam_id': steam_id,
                    'balance': 0,
                    'inventory': [],
                    'sales_history': []
                }).execute()
                logging.info(f"Новый пользователь добавлен: {steam_id}")
            
            redirect_url = f'https://cq34195.tw1.ru/?steamid={steam_id}&username={user_name}'
            logging.info(f"Перенаправление на: {redirect_url}")
            return redirect(redirect_url)
        else:
            logging.warning("Не удалось авторизоваться через Steam")
            return "Authentication failed", 400
    except Exception as e:
        logging.error(f"Ошибка в /auth: {str(e)}")
        return f"Ошибка: {str(e)}", 500

@app.route('/api/user')
def get_user():
    try:
        steam_id = request.args.get('steam_id')
        if not steam_id:
            logging.error("Missing steam_id in /api/user")
            return "Missing steam_id", 400
        
        response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
        if response.data:
            user = response.data[0]
            user_data = {
                'balance': user.get('balance', 0),
                'inventory': user.get('inventory', []),
                'sales_history': user.get('sales_history', [])
            }
            logging.info(f"Данные пользователя для {steam_id}: {user_data}")
            return jsonify(user_data)
        else:
            logging.warning(f"Пользователь не найден: {steam_id}")
            return "User not found", 404
    except Exception as e:
        logging.error(f"Ошибка в /api/user: {str(e)}")
        return f"Ошибка: {str(e)}", 500

@app.route('/api/user/update', methods=['POST'])
def update_user():
    try:
        data = request.get_json()
        steam_id = data.get('steam_id')
        if not steam_id:
            logging.error("Missing steam_id in /api/user/update")
            return "Missing steam_id", 400
        
        update_data = {}
        if 'balance' in data:
            update_data['balance'] = data['balance']
        if 'inventory' in data:
            update_data['inventory'] = data['inventory']
        if 'sales_history' in data:
            update_data['sales_history'] = data['sales_history']
        
        if update_data:
            supabase.table('users').update(update_data).eq('steam_id', steam_id).execute()
            logging.info(f"Данные обновлены для {steam_id}: {update_data}")
        else:
            logging.warning("Нет данных для обновления")
        
        return "User updated", 200
    except Exception as e:
        logging.error(f"Ошибка в /api/user/update: {str(e)}")
        return f"Ошибка: {str(e)}", 500

@app.route('/api/send-to-steam', methods=['POST'])
def send_to_steam():
    try:
        data = request.get_json()
        steam_id = data.get('steam_id')
        trade_url = data.get('trade_url')
        item = data.get('item')
        if not steam_id or not trade_url or not item:
            logging.error("Missing required fields in /api/send-to-steam")
            return "Missing required fields", 400
        
        logging.info(f"Отправка предмета {item['name']} для {steam_id}")
        return "Trade offer sent (placeholder)", 200
    except Exception as e:
        logging.error(f"Ошибка в /api/send-to-steam: {str(e)}")
        return f"Ошибка: {str(e)}", 500

if __name__ == '__main__':
    init_yoomoney_integration()
    if os.environ.get('FLASK_ENV') == 'development':
        socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
    else:
        logging.info("Запуск через gunicorn в продакшене")
