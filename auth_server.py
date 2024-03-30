#!/usr/bin/env python3
import os
import requests
import dotenv
import datetime
import webbrowser
import threading
from flask import Flask, request
from werkzeug.serving import make_server

os.chdir(os.path.dirname(os.path.abspath(__file__)))

dotenv.load_dotenv()

app = Flask(__name__)

token_acquired = threading.Event()
token_thread = None

@app.route('/')
def index():
    return "Authorization Server is running"

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if code:
        exchange_code_for_token(code)
        token_acquired.set()
        return 'Token acquired, shutting down server...'
    else:
        return 'Error: Code not received'

def get_auth_url():
    auth_url = 'https://www.facebook.com/v19.0/dialog/oauth'
    params = {
        'client_id': os.getenv('CLIENT_ID'),
        'redirect_uri': "https://"+os.getenv('CLIENT_IP_ADDRESS')+":5000/callback",
        'state': "{st=state123abc,ds=123456789}",
        'scope':"pages_show_list,business_management,instagram_basic",
        'response_type': 'code'
    }
    authorization_url = f"{auth_url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return authorization_url

def exchange_code_for_token(code):
    endpoint_url = 'https://graph.facebook.com/v19.0/oauth/access_token'
    params = {
        'client_id': os.getenv('CLIENT_ID'),
        'client_secret': os.getenv('CLIENT_SECRET'),
        'grant_type': 'authorization_code',
        'redirect_uri': 'https://'+os.getenv('CLIENT_IP_ADDRESS')+':5000/callback',
        'code': code
    }
    response = requests.post(endpoint_url, params=params)
    if response.status_code == 200:
        instagram_access_token = response.json()['access_token']
        expiry_date = datetime.datetime.now() + datetime.timedelta(seconds=response.json()['expires_in'])
        os.environ['LONG_ACCESS_TOKEN'] = instagram_access_token
        os.environ['LONG_ACCESS_TOKEN_EXPIRY'] = str(expiry_date)
        os.environ['IG_BUSINESS_USER_ID'] = ''
        dotenv.set_key('.env',"LONG_ACCESS_TOKEN", instagram_access_token)
        dotenv.set_key('.env',"LONG_ACCESS_TOKEN_EXPIRY", str(expiry_date))
        dotenv.set_key('.env',"IG_BUSINESS_USER_ID", os.environ['IG_BUSINESS_USER_ID'])
        return response.json()
    else:
        return 'Error: Failed to exchange authorization code for token'

def run_server():
    server = make_server(os.getenv('CLIENT_IP_ADDRESS'), 5000, app, ssl_context="adhoc")
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.start()
    return server, server_thread

def open_webbrowser(auth_url):
    webbrowser.open(auth_url, new=1, autoraise=True)

def wait_for_token():
    global token_thread

    token_acquired.clear()
    # Start server and server thread
    server, server_thread = run_server()
    token_acquired.wait()

    # Wait for token acquisition thread to complete
    token_thread.join() if token_thread else None
    server.shutdown()
    server_thread.join()

def native_capture(auth_url):
    global token_thread
    token_thread = threading.Thread(target=open_webbrowser, args=(auth_url,))
    token_thread.start()

def stop_server():
    if not token_acquired.is_set():
        token_acquired.set()

if __name__ == "__main__":
    auth_url = get_auth_url()
    native_capture(auth_url)
    wait_for_token()