import os
import json
import requests
import logging
from urllib.parse import urlencode, parse_qs, urlparse
from flask import Flask, redirect, request, jsonify, Response
from flask_cors import CORS
from supabase import create_client, Client

# Настройка логирования
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Настройка CORS для разрешения запросов с твоего сайта
CORS(app, resources={r"/api/*": {"origins": "https://cq34195.tw1.ru"}})

SUPABASE_URL = "https://gxeviitquermnukavhvj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4ZXZpaXRxdWVybW51a2F2aHZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI4MjY5NjgsImV4cCI6MjA1ODQwMjk2OH0.FOZnKiCzhL1UPVzOttN4RhFtrkplamHho6flpibdCx8"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/test')
def test():
    logging.info("Маршрут /test вызван")
    return "Сервер работает!"

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
        logging.info(f"Запрос на /login получен, Redirect URI: {redirect_url}")
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
            logging.info(f"Авторизация успешна, Steam ID: {steam_id}, Username: {user_name}")
            
            # Проверяем, есть ли пользователь в Supabase
            response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
            if not response.data:
                supabase.table('users').insert({
                    'steam_id': steam_id,
                    'balance': 0,
                    'inventory': [],
                    'sales_history': []
                }).execute()
                logging.info(f"Новый пользователь добавлен в Supabase: {steam_id}")
            
            # Перенаправляем на твой сайт с параметрами
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
            logging.info(f"Данные пользователя для steam_id {steam_id}: {user_data}")
            return jsonify(user_data)
        else:
            logging.warning(f"Пользователь не найден для steam_id {steam_id}")
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
            logging.info(f"Данные пользователя обновлены для steam_id {steam_id}: {update_data}")
        else:
            logging.warning("Нет данных для обновления в /api/user/update")
        
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
        
        logging.info(f"Отправка предмета {item['name']} пользователю {steam_id} через Trade URL: {trade_url}")
        return "Trade offer sent (placeholder)", 200
    except Exception as e:
        logging.error(f"Ошибка в /api/send-to-steam: {str(e)}")
        return f"Ошибка: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))
