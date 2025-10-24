import requests
from django.conf import settings
from datetime import datetime
from django.core.cache import cache
from .models import Team, Venue, Match, TicketPrice
from django.utils import timezone
import sys
import os
import json
from pathlib import Path

# --- KONSTANTA ---
CACHE_KEY_SYNC = 'full_match_sync_data'
CACHE_TIMEOUT = 60 * 60 * 24

# Mendefinisikan Path untuk JSON Backup
JSON_DIR = Path(os.path.abspath(__file__)).parent / 'manage_db'
JSON_FILE_PATH = JSON_DIR / 'matches_backup.json'

# --- LOGIKA JSON BACKUP ---

def _save_to_json(data):
    """Menyimpan data pertandingan ke JSON file (cache permanen)."""
    if not JSON_DIR.exists():
        os.makedirs(JSON_DIR)
        
    try:
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"-> JSON: Data berhasil disimpan ke {JSON_FILE_PATH}")
        return True
    except Exception as e:
        print(f"-> JSON: Gagal menyimpan data ke JSON file: {e}")
        return False

def _load_from_json():
    """Memuat data pertandingan dari JSON file (cache permanen)."""
    if not JSON_FILE_PATH.exists():
        print("-> JSON: File backup tidak ditemukan.")
        return None
        
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"-> JSON: Berhasil memuat {len(data)} pertandingan dari backup JSON.")
        return data
    except Exception as e:
        print(f"-> JSON: Gagal membaca atau mem-parse JSON file: {e}")
        return None

# --- PEMETAAN NAMA TIM SECARA HARDCODE ---
TEAM_NAME_STANDARDIZATION = {
    # 1
    "arema": "Arema FC",
    "arema fc": "Arema FC",

    # 2
    "bali united": "Bali United FC",
    "bali united fc": "Bali United FC",
    # ... (Dipotong untuk efisiensi, asumsikan sama dengan file yang Anda miliki)
    # ...
    # 18
    "semen padang": "Semen Padang FC",
    "semen padang fc": "Semen Padang FC",
    
    # Tim tidak bermain di liga super 2025
    "psis semarang": "PSIS Semarang",
    "pss sleman": "PSS Sleman",
    "cilegon united": "Cilegon United",
    "ps tira": "PS TIRA",
    "barito putera": "PS Barito Putera",
}

# -------------------------- DEFINISI TIM LIGA 1 --------------------------
LIGA_1_TEAMS = {
    "Arema FC", "Bali United FC", "Bhayangkara Presisi Lampung FC", 
    "Borneo Samarinda FC", "Dewa United Banten FC", "Madura United FC", 
    "Malut United FC", "Persebaya Surabaya", "Persib Bandung", 
    "Persija Jakarta", "Persik Kediri", "Persis Solo", 
    "Persita Tangerang", "PSBS Biak Numfor", "PSIM Yogyakarta", 
    "PSM Makassar", "Semen Padang FC", "Persijap Jepara"
}
# --------------------------------------------------------------------------

def _fetch_freeapi_matches(league_id=8983):
    url = "https://free-api-live-football-data.p.rapidapi.com/football-get-all-matches-by-league"
    headers = {
        "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
        "x-rapidapi-key": settings.RAPID_API_KEY
    }
    params = {"leagueid": league_id}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status() 
        
        json_data = response.json()
        if json_data.get('status') == 'failed':
             print(f"Error fetching data from FreeAPI: {json_data.get('message', 'Request failed (unknown reason)')}")
             return []

        data = json_data.get('response', {}).get('matches', [])
        print(f"-> API: Berhasil mengambil {len(data)} pertandingan.")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching data from FreeAPI: {e}")
        if e.response.status_code == 429:
            print("Error 429: Rate limit tercapai. Mencoba memuat dari cache.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from FreeAPI: {e}")
        return []
    except Exception as e:
        print(f"Error processing JSON response from FreeAPI: {e}")
        return []

def _clean_team_name(name):
    if name is None:
        return None
    clean_key = name.lower().strip()
    return TEAM_NAME_STANDARDIZATION.get(clean_key, name.strip().title())

def _normalize_match_data(raw_match):
    try:
        home_team_name_raw = raw_match['home']['name']
        away_team_name_raw = raw_match['away']['name']
        
        home_team_name_clean = _clean_team_name(home_team_name_raw)
        away_team_name_clean = _clean_team_name(away_team_name_raw)
        
        # Mengambil skor
        home_score = raw_match['home'].get('score')
        away_score = raw_match['away'].get('score')

        home_goals = int(home_score) if home_score is not None else None
        away_goals = int(away_score) if away_score is not None else None
        
        return {
            'id': raw_match['id'], 
            'date_str': raw_match['status']['utcTime'],
            'home_team': home_team_name_clean, 
            'away_team': away_team_name_clean, 
            'home_goals': home_goals, 
            'away_goals': away_goals,
            'venue': raw_match.get('venue'),
            'city': raw_match.get('city'),
            'home_team_api_id': raw_match['home']['id'], 
            'away_team_api_id': raw_match['away']['id'],
        }
    except (KeyError, TypeError, AttributeError) as e:
        print(f"Error normalizing match data: {e}")
        return None

def _get_sync_data():
    """Prioritas: Django Cache -> JSON Backup -> External API"""
    
    # 1. Cek Django Cache (Cache cepat/expiring)
    cached_matches = cache.get(CACHE_KEY_SYNC)
    if cached_matches:
        print("-> STATUS: Cache Hit (Django Cache).")
        return cached_matches
        
    # 2. Cek JSON Backup (Cache permanen/non-expiring)
    print("-> STATUS: Django Cache Miss. Mencoba memuat dari JSON Backup...")
    data_from_json = _load_from_json()
    if data_from_json:
        # Jika JSON berhasil, simpan ke Django cache untuk mempercepat akses berikutnya
        cache.set(CACHE_KEY_SYNC, data_from_json, timeout=CACHE_TIMEOUT)
        print("-> CACHE: JSON Backup berhasil dimuat ke Django Cache.")
        return data_from_json
        
    # 3. Ambil dari External API
    print("-> STATUS: JSON Backup Gagal/Tidak Ada. Mengambil data dari API...")
    raw_free_api_data = _fetch_freeapi_matches()
    
    all_matches = []
    processed_ids = set()
    
    for match in raw_free_api_data:
        normalized = _normalize_match_data(match)
        if normalized and normalized['id'] not in processed_ids:
            all_matches.append(normalized)
            processed_ids.add(normalized['id'])

    if all_matches:
        # Jika API berhasil, simpan ke Django Cache DAN JSON backup
        cache.set(CACHE_KEY_SYNC, all_matches, timeout=CACHE_TIMEOUT)
        _save_to_json(all_matches)
        print(f"-> CACHE & JSON: Data {len(all_matches)} BARU berhasil disimpan.")
        return all_matches
    
    print("-> ERROR: Gagal mendapatkan data dari semua sumber.")
    return []

# --- FUNGSI UTAMA SINKRONISASI ---
def sync_database_with_apis():
    print("=========================================")
    print("Memulai sinkronisasi database dengan API/Cache/JSON...")
    
    data_to_sync = _get_sync_data()
    
    if not data_to_sync:
        print("-> DB: Data untuk disinkronisasi kosong. Proses DB Write dilewati.")
        print("=========================================")
        print("Sinkronisasi database selesai.")
        print("=========================================\n")
        return
    
    print(f"-> DB: Memulai pembaruan/pembuatan {len(data_to_sync)} entri database...")
    
    matches_updated_count = 0
    matches_created_count = 0
    
    for match_data in data_to_sync:
        match_id = match_data.get('id', 'N/A')
        
        # ... (Logika pemrosesan data ke DB) ...
        # (Asumsi logika ini tidak perlu diulang di sini, karena sudah ada di services.py sebelumnya)
        
        if not all([match_data.get('home_team_api_id'), match_data.get('away_team_api_id'), match_data.get('id')]):
            print(f"-> DEBUG: SKIPPED Match ID {match_id}: Missing one or more critical API IDs (Home/Away/Match).")
            continue

        home_team_name = match_data.get('home_team')
        away_team_name = match_data.get('away_team')
        
        if not home_team_name or not away_team_name:
            print(f"-> DEBUG: SKIPPED Match ID {match_id}: Missing cleaned team name. Home: {home_team_name}, Away: {away_team_name}")
            continue
        
        try:
            # Perhatikan: Logika ini identik dengan yang sudah Anda miliki (termasuk error handling per item)
            venue_name_final = match_data.get('venue') or 'Unknown Stadium'
            venue_city_final = match_data.get('city') or 'Unknown City'
            
            venue, _ = Venue.objects.get_or_create(
                name=venue_name_final,
                defaults={
                    'city': venue_city_final,
                }
            )
            
            home_league = 'liga_1' if home_team_name in LIGA_1_TEAMS else 'n/a'
            
            home_team, created_home = Team.objects.update_or_create(
                name=home_team_name,
                defaults={
                    'api_id': match_data.get('home_team_api_id'),
                    'logo_url': None, 
                    'league': home_league, 
                }
            )
            
            away_team_name = match_data.get('away_team')
            away_league = 'liga_1' if away_team_name in LIGA_1_TEAMS else 'n/a'
            
            away_team, created_away = Team.objects.update_or_create(
                name=away_team_name,
                defaults={
                    'api_id': match_data.get('away_team_api_id'),
                    'logo_url': None, 
                    'league': away_league, 
                }
            )

            match_datetime = datetime.fromisoformat(match_data['date_str'].replace('Z', '+00:00'))
            
            home_goals = match_data.get('home_goals')
            away_goals = match_data.get('away_goals')

            match, created = Match.objects.update_or_create(
                api_id=match_data.get('id'),
                defaults={
                    'home_team': home_team, 'away_team': away_team, 'venue': venue, 'date': match_datetime,
                    'status_short': "FT" if home_goals is not None else "NS",
                    'status_long': "Match Finished" if home_goals is not None else "Not Started",
                    'home_goals': home_goals, 
                    'away_goals': away_goals,
                }
            )
            
            if created:
                matches_created_count += 1
                TicketPrice.objects.create(match=match, seat_category='VVIP', price=500000, quantity_available=50)
                TicketPrice.objects.create(match=match, seat_category='VIP', price=300000, quantity_available=200)
                TicketPrice.objects.create(match=match, seat_category='REGULAR', price=150000, quantity_available=1000)
            else:
                matches_updated_count += 1

        except Exception as e:
            print(f"!!! FATAL DB WRITE ERROR for Match ID {match_id} ({home_team_name} vs {away_team_name}): {e}")
            continue

    print(f"-> DB: Total Pertandingan Diproses: {len(data_to_sync)}")
    print(f"-> DB: Created: {matches_created_count}, Updated: {matches_updated_count}")
    print("=========================================")
    print("Sinkronisasi database selesai.")
    print("=========================================\n")