import os
import json
import requests
from urllib.parse import urlencode, parse_qs, urlparse
from flask import Flask, redirect, request, jsonify, Response
from supabase import create_client, Client

app = Flask(__name__)

SUPABASE_URL = "https://gxeviitquermnukavhvj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4ZXZpaXRxdWVybW51a2F2aHZqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI4MjY5NjgsImV4cCI6MjA1ODQwMjk2OH0.FOZnKiCzhL1UPVzOttN4RhFtrkplamHho6flpibdCx8"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/test')
def test():
    with open('/home/dimahacker3000krut/app.log', 'a') as f:
        f.write("Маршрут /test вызван\n")
    return "Сервер работает!"

@app.route('/login')
def login():
    steam_login_url = 'https://steamcommunity.com/openid/login'
    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.return_to': 'https://dimahacker3000krut.pythonanywhere.com/auth',
        'openid.realm': 'https://dimahacker3000krut.pythonanywhere.com',
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select',
    }
    redirect_url = f"{steam_login_url}?{urlencode(params)}"
    with open('/home/dimahacker3000krut/app.log', 'a') as f:
        f.write(f"Запрос на /login получен\nRedirect URI: {redirect_url}\n")
    return redirect(redirect_url)

@app.route('/auth')
def auth():
    query = urlparse(request.url).query
    params = parse_qs(query)
    params['openid.mode'] = 'check_authentication'
    
    response = requests.get('https://steamcommunity.com/openid/login', params=params)
    
    if 'is_valid:true' in response.text:
        steam_id = params['openid.claimed_id'][0].split('/')[-1]
        user_name = f"User_{steam_id[-4:]}"
        response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
        if not response.data:
            supabase.table('users').insert({
                'steam_id': steam_id,
                'balance': 0,
                'inventory': [],
                'sales_history': []
            }).execute()
        redirect_url = f'/index.html?steamid={steam_id}&username={user_name}'
        return redirect(redirect_url)
    else:
        return "Authentication failed", 400

@app.route('/api/user')
def get_user():
    steam_id = request.args.get('steam_id')
    if not steam_id:
        return "Missing steam_id", 400
    response = supabase.table('users').select('*').eq('steam_id', steam_id).execute()
    if response.data:
        user = response.data[0]
        user_data = {
            'balance': user.get('balance', 0),
            'inventory': user.get('inventory', []),
            'sales_history': user.get('sales_history', [])
        }
        return jsonify(user_data)
    else:
        return "User not found", 404

@app.route('/api/user/update', methods=['POST'])
def update_user():
    data = request.get_json()
    steam_id = data.get('steam_id')
    if not steam_id:
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
    return "User updated", 200

@app.route('/api/send-to-steam', methods=['POST'])
def send_to_steam():
    data = request.get_json()
    steam_id = data.get('steam_id')
    trade_url = data.get('trade_url')
    item = data.get('item')
    if not steam_id or not trade_url or not item:
        return "Missing required fields", 400
    print(f"Отправка предмета {item['name']} пользователю {steam_id} через Trade URL: {trade_url}")
    return "Trade offer sent (placeholder)", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)