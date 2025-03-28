import os
import logging
import json
import requests
from flask import Flask, request, redirect, url_for, jsonify
from flask_socketio import SocketIO
from supabase import create_client, Client
from threading import Thread
import time

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация Flask и SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6')
socketio = SocketIO(app, cors_allowed_origins="https://cq34195.tw1.ru", logger=True, engineio_logger=True)

# Инициализация Supabase
SUPABASE_URL = "https://gxeviitquermnukavhvj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4ZXZpaXRxdWVybW51a2F2aHZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mjg5OTU5MDcsImV4cCI6MjA0NDU3MTkwN30.-I6lWJwDi6zTzzXh0gT6W2iM7nW9K2x2L2x2L2x2L2w"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.info("Supabase клиент успешно инициализирован")

# Настройки DonationAlerts OAuth
CLIENT_ID = "14690"  # Замените на ваш client_id
CLIENT_SECRET = "YIJUslJ5md0wvPfQK8D0dIop3faLh54dWCAcoWZB"  # Замените на ваш client_secret
REDIRECT_URI = "https://cs2cases.onrender.com/oauth/callback"
DA_AUTH_URL = "https://www.donationalerts.com/oauth/authorize"
DA_TOKEN_URL = "https://www.donationalerts.com/oauth/token"
DA_WS_URL = "wss://socket.donationalerts.ru:443"

# Переменная для хранения access_token
access_token = None

# Функция для сохранения refresh_token в Supabase
def save_refresh_token(refresh_token):
    response = supabase.table('tokens').select('*').eq('id', 1).execute()
    if response.data:
        supabase.table('tokens').update({
            'refresh_token': refresh_token,
            'updated_at': 'now()'
        }).eq('id', 1).execute()
    else:
        supabase.table('tokens').insert({
            'id': 1,
            'refresh_token': refresh_token,
            'updated_at': 'now()'
        }).execute()
    logging.info("refresh_token сохранён в Supabase")

# Функция для получения refresh_token из Supabase
def get_refresh_token():
    response = supabase.table('tokens').select('refresh_token').eq('id', 1).execute()
    if response.data:
        return response.data[0]['refresh_token']
    return None

# Маршрут для начала авторизации
@app.route('/oauth/login')
def oauth_login():
    auth_url = (
        f"{DA_AUTH_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
        "&response_type=code&scope=oauth-donation-index oauth-user-show"
    )
    logging.info(f"Перенаправление на авторизацию: {auth_url}")
    return redirect(auth_url)

# Маршрут для обработки callback после авторизации
@app.route('/oauth/callback')
def oauth_callback():
    global access_token
    try:
        code = request.args.get('code')
        if not code:
            logging.error("Параметр 'code' отсутствует в запросе")
            return "Ошибка: код авторизации не получен", 400

        logging.info(f"Получен код авторизации: {code}")

        token_data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        }
        logging.info(f"Отправка запроса на {DA_TOKEN_URL} с данными: {token_data}")
        response = requests.post(DA_TOKEN_URL, data=token_data)
        
        if response.status_code != 200:
            logging.error(f"Ошибка получения токена: {response.status_code} - {response.text}")
            return "Ошибка получения токена", 500

        try:
            token_response = response.json()
        except ValueError as e:
            logging.error(f"Ошибка парсинга JSON ответа: {str(e)}")
            return "Ошибка: некорректный JSON в ответе от DonationAlerts", 500

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")

        if not access_token or not refresh_token:
            logging.error(f"access_token или refresh_token отсутствуют в ответе: {token_response}")
            return "Ошибка: токены не получены", 500

        logging.info(f"Получен access_token: {access_token}")

        try:
            save_refresh_token(refresh_token)
        except Exception as e:
            logging.error(f"Ошибка сохранения refresh_token в Supabase: {str(e)}")
            return "Ошибка сохранения refresh_token", 500

        init_donation_alerts()
        return "Авторизация успешна. Теперь сервер может получать донаты."

    except Exception as e:
        logging.error(f"Необработанная ошибка в /oauth/callback: {str(e)}")
        return f"Произошла ошибка: {str(e)}", 500

# Функция для обновления access_token
def refresh_access_token():
    global access_token
    refresh_token = get_refresh_token()
    if not refresh_token:
        logging.error("refresh_token не найден в Supabase")
        return False

    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    response = requests.post(DA_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        logging.error(f"Ошибка обновления токена: {response.text}")
        return False

    token_response = response.json()
    access_token = token_response.get("access_token")
    new_refresh_token = token_response.get("refresh_token")
    logging.info(f"Токен обновлен: {access_token}")
    save_refresh_token(new_refresh_token)
    return True

# Функция для сохранения доната
def save_donation(steam_id, amount, currency):
    try:
        supabase.table('donations').insert({
            'steam_id': steam_id,
            'amount': amount,
            'currency': currency,
            'created_at': 'now()'
        }).execute()
        logging.info(f"Донат сохранён: {steam_id}, {amount} {currency}")
    except Exception as e:
        logging.error(f"Ошибка сохранения доната: {str(e)}")

# Инициализация WebSocket-соединения с DonationAlerts
def init_donation_alerts():
    if not access_token:
        logging.error("access_token не установлен")
        return

    @socketio.on('connect')
    def on_connect():
        logging.info("Подключено к DonationAlerts")
        socketio.emit('add-user', {'token': access_token, 'type': 'minor'})

    @socketio.on('donation')
    def on_donation(data):
        try:
            donation = json.loads(data)
            logging.info(f"Новый донат: {donation}")
            
            steam_id = donation.get('username')
            if not steam_id:
                logging.warning("SteamID не указан в имени доната")
                return
            
            amount = int(donation['amount'])  # Используем int, так как balance — int4
            currency = donation['currency']
            amount_in_rub = amount
            if currency != 'RUB':
                rates = {'USD': 90, 'EUR': 100}
                amount_in_rub = amount * rates.get(currency, 1)
                logging.info(f"Конвертация: {amount} {currency} -> {amount_in_rub} RUB")

            save_donation(steam_id, amount_in_rub, currency)

            response = supabase.table('users').select('balance').eq('steam_id', steam_id).execute()
            if response.data:
                new_balance = response.data[0]['balance'] + amount_in_rub
                supabase.table('users').update({'balance': new_balance}).eq('steam_id', steam_id).execute()
                logging.info(f"Баланс обновлен для {steam_id}: {new_balance}")
                socketio.emit('balance_update', {'steam_id': steam_id, 'balance': new_balance})
            else:
                supabase.table('users').insert({
                    'steam_id': steam_id,
                    'balance': amount_in_rub,
                    'inventory': [],
                    'sales_history': []
                }).execute()
                logging.info(f"Создан пользователь {steam_id} с балансом {amount_in_rub}")
                socketio.emit('balance_update', {'steam_id': steam_id, 'balance': amount_in_rub})
        except Exception as e:
            logging.error(f"Ошибка при обработке доната: {str(e)}")

    @socketio.on('error')
    def on_error(error):
        logging.error(f"Ошибка SocketIO: {error}")

    @socketio.on('disconnect')
    def on_disconnect():
        logging.info("Отключено от DonationAlerts")

    Thread(target=poll_donations, daemon=True).start()

# Резервный способ опроса донатов через API
def poll_donations():
    global access_token
    while True:
        try:
            if not access_token:
                logging.error("access_token не установлен для опроса донатов")
                time.sleep(300)
                continue

            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get('https://www.donationalerts.com/api/v1/alerts/donations', headers=headers)
            if response.status_code == 401:
                if refresh_access_token():
                    continue
                else:
                    time.sleep(300)
                    continue

            response.raise_for_status()
            donations = response.json().get('data', [])
            
            for donation in donations:
                steam_id = donation.get('username')
                if not steam_id:
                    logging.warning("SteamID не указан в имени доната (API)")
                    continue
                
                amount = int(donation['amount'])  # Используем int
                currency = donation['currency']
                amount_in_rub = amount
                if currency != 'RUB':
                    rates = {'USD': 90, 'EUR': 100}
                    amount_in_rub = amount * rates.get(currency, 1)

                save_donation(steam_id, amount_in_rub, currency)

                response = supabase.table('users').select('balance').eq('steam_id', steam_id).execute()
                if response.data:
                    new_balance = response.data[0]['balance'] + amount_in_rub
                    supabase.table('users').update({'balance': new_balance}).eq('steam_id', steam_id).execute()
                    logging.info(f"Баланс обновлен для {steam_id} (API): {new_balance}")
                    socketio.emit('balance_update', {'steam_id': steam_id, 'balance': new_balance})
                else:
                    supabase.table('users').insert({
                        'steam_id': steam_id,
                        'balance': amount_in_rub,
                        'inventory': [],
                        'sales_history': []
                    }).execute()
                    logging.info(f"Создан пользователь {steam_id} с балансом {amount_in_rub} (API)")
                    socketio.emit('balance_update', {'steam_id': steam_id, 'balance': amount_in_rub})
        except Exception as e:
            logging.error(f"Ошибка при опросе донатов через API: {str(e)}")
        time.sleep(300)

# API для получения данных пользователя
@app.route('/api/user', methods=['GET'])
def get_user():
    steam_id = request.args.get('steam_id')
    if not steam_id:
        return {"error": "SteamID не указан"}, 400

    response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
    if response.data:
        user_data = response.data[0]
        logging.info(f"Данные пользователя для {steam_id}: {user_data}")
        return user_data, 200
    else:
        return {"error": "Пользователь не найден"}, 404

# API для обновления данных пользователя
@app.route('/api/user/update', methods=['POST'])
def update_user():
    data = request.get_json()
    steam_id = data.get('steam_id')
    balance = data.get('balance')
    inventory = data.get('inventory')
    sales_history = data.get('sales_history')

    if not steam_id:
        return {"error": "SteamID не указан"}, 400

    try:
        # Проверяем, существует ли пользователь
        response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
        if not response.data:
            return {"error": "Пользователь не найден"}, 404

        # Обновляем данные
        update_data = {}
        if balance is not None:
            update_data['balance'] = int(balance)  # Убедимся, что balance — целое число
        if inventory is not None:
            update_data['inventory'] = inventory
        if sales_history is not None:
            update_data['sales_history'] = sales_history

        supabase.table('users').update(update_data).eq('steam_id', steam_id).execute()
        logging.info(f"Данные пользователя {steam_id} обновлены")
        socketio.emit('balance_update', {'steam_id': steam_id, 'balance': balance})
        return {"message": "Данные обновлены"}, 200
    except Exception as e:
        logging.error(f"Ошибка обновления данных пользователя: {str(e)}")
        return {"error": str(e)}, 500

# API для добавления предмета в инвентарь
@app.route('/api/inventory/add', methods=['POST'])
def add_inventory_item():
    data = request.get_json()
    steam_id = data.get('steam_id')
    item_name = data.get('item_name')
    item_type = data.get('item_type')
    price = data.get('price')
    image = data.get('image')  # Добавляем поле для изображения

    if not all([steam_id, item_name, item_type, price, image]):
        return {"error": "Все поля (steam_id, item_name, item_type, price, image) обязательны"}, 400

    try:
        # Получаем текущий инвентарь пользователя
        response = supabase.table('users').select('inventory').eq('steam_id', steam_id).execute()
        if not response.data:
            return {"error": "Пользователь не найден"}, 404

        current_inventory = response.data[0]['inventory'] or []
        
        # Генерируем уникальный ID для предмета
        max_id = max([item.get('id', 0) for item in current_inventory], default=0)
        new_item = {
            'id': max_id + 1,
            'name': item_name,  # Используем "name" вместо "item_name" для соответствия фронтенду
            'type': item_type,
            'price': int(price),  # Используем int, так как balance — int4
            'image': image,
            'status': 'available'
        }

        # Добавляем новый предмет в инвентарь
        current_inventory.append(new_item)
        supabase.table('users').update({'inventory': current_inventory}).eq('steam_id', steam_id).execute()
        logging.info(f"Предмет добавлен в инвентарь: {item_name} для {steam_id}")
        return {"message": "Предмет добавлен", "item": new_item}, 201
    except Exception as e:
        logging.error(f"Ошибка добавления предмета: {str(e)}")
        return {"error": str(e)}, 500

# API для отправки предмета в Steam (заглушка)
@app.route('/api/send-to-steam', methods=['POST'])
def send_to_steam():
    data = request.get_json()
    steam_id = data.get('steam_id')
    trade_url = data.get('trade_url')
    item = data.get('item')

    if not all([steam_id, trade_url, item]):
        return {"error": "Все поля (steam_id, trade_url, item) обязательны"}, 400

    try:
        # Проверяем, существует ли пользователь
        response = supabase.table('users').select('inventory').eq('steam_id', steam_id).execute()
        if not response.data:
            return {"error": "Пользователь не найден"}, 404

        inventory = response.data[0]['inventory'] or []
        item_found = False
        for inv_item in inventory:
            if inv_item['id'] == item['id'] and inv_item['status'] == 'available':
                inv_item['status'] = 'sent'
                item_found = True
                break

        if not item_found:
            return {"error": "Предмет не найден или уже отправлен"}, 404

        # Обновляем инвентарь
        supabase.table('users').update({'inventory': inventory}).eq('steam_id', steam_id).execute()

        # Здесь должна быть реальная интеграция с Steam Trade API
        # Для примера просто логируем
        logging.info(f"Предмет {item['name']} отправлен в Steam для {steam_id} по Trade URL: {trade_url}")
        return {"message": "Предмет отправлен в Steam"}, 200
    except Exception as e:
        logging.error(f"Ошибка отправки предмета в Steam: {str(e)}")
        return {"error": str(e)}, 500

# Запуск приложения
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=10000)
