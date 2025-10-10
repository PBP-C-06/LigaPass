import requests
from django.conf import settings
from datetime import datetime
import json
from pathlib import Path

# --- Caching Configuration ---
# File cache akan disimpan di root proyek (BASE_DIR)
CACHE_FILE = Path(settings.BASE_DIR) / 'match_cache.json'
CACHE_EXPIRY = 86400 # Waktu kedaluwarsa cache dalam detik (24 jam/Harian)
# ---------------------------

API_URL = "https://v3.football.api-sports.io/" 

LIGA_ID = 274 # ID Liga 1 api football v3
SEASON = 2023
# SEASON = datetime.now().year 

def fetch_upcoming_matches(league_id=LIGA_ID, season=SEASON):
    # --- Caching Check ---
    if CACHE_FILE.exists():
        try:
            # Membaca data dari file cache
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
            
            cache_time = data.get('timestamp', 0)
            
            # Cek apakah cache masih valid
            if datetime.now().timestamp() < cache_time + CACHE_EXPIRY:
                print("Mengambil data dari cache...")
                return data.get('response', [])
        
        except (json.JSONDecodeError, FileNotFoundError, IOError) as e:
            # Jika file cache rusak atau error membaca, abaikan dan lanjutkan ke API call
            print(f"Cache file error: {e}. Fetching from API...")
            pass
    # -------------------
    
    url = f"{API_URL}fixtures"
    
    # Header yang diperlukan untuk otorisasi API-Football
    HEADERS = {
        'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    # Parameter untuk mendapatkan pertandingan liga tertentu
    params = {
        'league': league_id,
        'season': season,
        # 'status': 'NS', # Not Started (Akan datang)
        'timezone': 'Asia/Jakarta', # Sesuaikan zona waktu Indonesia
        # 'next': 20 # Ambil 20 pertandingan berikutnya
    }

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status() # Tangani error HTTP (4xx atau 5xx)
        data = response.json()
        
        # --- Cache Save ---
        if data.get('response'):
            cache_data = {
                'timestamp': datetime.now().timestamp(),
                'response': data['response']
            }
            # Tulis data baru ke cache
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
        # ------------------
        
        return data['response'] if data.get('response') else []
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API-Football: {e}")
        # Kembalikan list kosong jika ada error
        return []