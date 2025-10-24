import requests
from django.conf import settings
from datetime import datetime
from .models import Team, Venue, Match, TicketPrice
from django.utils import timezone
import sys
import os
import json
from pathlib import Path

# --- KONSTANTA ---
JSON_DIR = Path(os.path.abspath(__file__)).parent / 'manage_db'
# Path untuk cache data yang sudah dinormalisasi dari API
API_CACHE_FILE_PATH = JSON_DIR / 'matches_backup.json' 
# Path untuk file fixture database (data mentah)
DB_FIXTURE_PATH = JSON_DIR / 'db_backup.json' 

# --- LOGIKA JSON (API CACHE) ---
def _save_to_api_cache(data):
    """Menyimpan data pertandingan yang dinormalisasi ke JSON file (sebagai API cache/fallback)."""
    if not JSON_DIR.exists():
        os.makedirs(JSON_DIR)
        
    try:
        with open(API_CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"-> JSON: Data API berhasil disimpan ke {API_CACHE_FILE_PATH}")
        return True
    except Exception as e:
        print(f"-> JSON: Gagal menyimpan data ke JSON cache file: {e}")
        return False

def _load_from_api_cache():
    """Memuat data pertandingan dari JSON file (fallback jika API gagal)."""
    if not API_CACHE_FILE_PATH.exists():
        print(f"-> JSON: File API cache ({API_CACHE_FILE_PATH.name}) tidak ditemukan.")
        return None
        
    try:
        with open(API_CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"-> JSON: Berhasil memuat {len(data)} pertandingan dari API cache.")
        return data
    except Exception as e:
        print(f"-> JSON: Gagal membaca atau mem-parse API cache file: {e}")
        return None

# --- LOGIKA JSON (DB FIXTURE FALLBACK) ---

def _load_from_fixture_json():
    """Memuat dan mentransformasi data dari file fixture db_backup.json."""
    if not DB_FIXTURE_PATH.exists():
        print(f"-> JSON: File DB fixture ({DB_FIXTURE_PATH.name}) tidak ditemukan.")
        return None
    
    try:
        with open(DB_FIXTURE_PATH, 'r', encoding='utf-8') as f:
            fixture_data = json.load(f)

        print(f"-> JSON: Membaca file DB fixture ({DB_FIXTURE_PATH.name})...")
        
        # Pisahkan data berdasarkan model untuk memetakan relasi
        teams = {}
        venues = {}
        matches_fixture = []

        for item in fixture_data:
            if item.get('model') == 'matches.team':
                teams[item['pk']] = item['fields']
            elif item.get('model') == 'matches.venue':
                venues[item['pk']] = item['fields']
            elif item.get('model') == 'matches.match':
                matches_fixture.append(item)

        # Transformasi data match ke format yang diharapkan
        normalized_matches = []
        for match_item in matches_fixture:
            fields = match_item['fields']
            
            home_team_data = teams.get(fields.get('home_team'))
            away_team_data = teams.get(fields.get('away_team'))
            venue_data = venues.get(fields.get('venue'))

            # Jika data relasi tidak lengkap di fixture, lewati
            if not all([home_team_data, away_team_data, venue_data]):
                print(f"-> JSON: Melewatkan fixture match (PK: {match_item['pk']}) karena data tim/venue tidak ada di fixture.")
                continue

            normalized_match = {
                'id': fields['api_id'],
                'date_str': fields['date'],
                'home_team': home_team_data['name'],
                'away_team': away_team_data['name'],
                'home_goals': fields.get('home_goals'),
                'away_goals': fields.get('away_goals'),
                'venue': venue_data.get('name', 'Unknown Stadium'),
                'city': venue_data.get('city', 'Unknown City'),
                'home_team_api_id': home_team_data['api_id'],
                'away_team_api_id': away_team_data['api_id'],
            }
            normalized_matches.append(normalized_match)
        
        print(f"-> JSON: Berhasil memuat dan mentransformasi {len(normalized_matches)} pertandingan dari DB fixture.")
        return normalized_matches

    except Exception as e:
        print(f"-> JSON: Gagal membaca atau mem-parse DB fixture file: {e}")
        return None


# --- PEMETAAN NAMA TIM SECARA HARDCODE ---
TEAM_NAME_STANDARDIZATION = {
    # 1
    "arema": "Arema FC",
    "arema fc": "Arema FC",
    # 2
    "bali united": "Bali United FC",
    "bali united fc": "Bali United FC",
    # 3
    "bhayangkara": "Bhayangkara Presisi Lampung FC",
    "bhayangkara fc": "Bhayangkara Presisi Lampung FC",
    "bhayangkara presisi indonesia": "Bhayangkara Presisi Lampung FC",
    "bhayangkara presisi indonesia fc": "Bhayangkara Presisi Lampung FC",
    #4
    "pusamania borneo": "Borneo Samarinda FC",
    "borneo samarinda": "Borneo Samarinda FC",
    # 5
    "dewa united": "Dewa United Banten FC",
    "dewa united fc": "Dewa United Banten FC",
    # 6
    "madura united": "Madura United FC",
    "persepam madura utd": "Madura United FC",
    # 7
    "malut united": "Malut United FC",
    # 8
    "persebaya surabaya": "Persebaya Surabaya",
    # 9
    "persib bandung": "Persib Bandung",
    # 10
    "persija jakarta": "Persija Jakarta",
    # 11
    "persijap jepara": "Persijap Jepara",
    # 12
    "persik": "Persik Kediri",
    "persik kediri": "Persik Kediri",
    # 13
    "persis solo": "Persis Solo",
    # 14
    "persita": "Persita Tangerang",
    # 15
    "psbs biak numfor": "PSBS Biak Numfor",
    # 16
    "psim yogyakarta": "PSIM Yogyakarta",
    # 17
    "psm makassar": "PSM Makassar",
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
    """Mencoba mengambil data pertandingan dari API eksternal."""
    url = "https://free-api-live-football-data.p.rapidapi.com/football-get-all-matches-by-league"
    headers = {
        "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
        "x-rapidapi-key": settings.RAPID_API_KEY
    }
    params = {"leagueid": league_id}
    try:
        print("-> API: Mencoba mengambil data dari FreeAPI...")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status() 
        
        json_data = response.json()
        if json_data.get('status') == 'failed':
            print(f"-> API: Gagal mengambil data: {json_data.get('message', 'Request failed (unknown reason)')}")
            return [] 

        data = json_data.get('response', {}).get('matches', [])
        print(f"-> API: Berhasil mengambil {len(data)} pertandingan.")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"-> API: Gagal mengambil data (HTTP Error {e.response.status_code}): {e}")
        if e.response.status_code == 429:
            print("-> API: Error 429 - Rate limit tercapai.")
        return [] 
    except requests.exceptions.RequestException as e:
        print(f"-> API: Gagal mengambil data (Request Exception): {e}")
        return [] 
    except Exception as e:
        print(f"-> API: Gagal memproses response JSON: {e}")
        return [] 

def _clean_team_name(name):
    """Membersihkan dan menstandarkan nama tim."""
    if name is None:
        return None
    clean_key = name.lower().strip()
    return TEAM_NAME_STANDARDIZATION.get(clean_key, name.strip().title())

def _normalize_match_data(raw_match):
    """Mengubah format data mentah dari API menjadi format yang lebih terstruktur. (normalisasi data)"""
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
        print(f"Error normalizing match data (ID: {raw_match.get('id', 'N/A')}): {e}")
        return None

def _get_sync_data():
    """
    Mendapatkan data untuk sinkronisasi dengan prioritas sebagai berikut:  
    1. External API
    2. API Cache (matches_backup.json)
    3. DB Fixture (db_backup.json)
    """
    
    all_matches = []
    processed_ids = set()

    # 1 - Coba ambil dari External API
    print("-> STATUS: Mengambil data dari API...")
    raw_api_data = _fetch_freeapi_matches()

    if raw_api_data: # Jika API berhasil dan mengembalikan data
        print(f"-> STATUS: API berhasil, memproses {len(raw_api_data)} data mentah.")
        for match in raw_api_data:
            normalized = _normalize_match_data(match)
            if normalized and normalized.get('id') and normalized['id'] not in processed_ids:
                all_matches.append(normalized)
                processed_ids.add(normalized['id'])
        
        if all_matches:
            print(f"-> STATUS: Normalisasi API berhasil untuk {len(all_matches)} pertandingan.")
            _save_to_api_cache(all_matches) # Simpan ke cache API
            print("-> SUMBER DATA: Menggunakan data dari API.")
            return all_matches, "api_live"
        else:
            print("-> PERINGATAN: Data API ada tapi tidak valid setelah normalisasi. Mencoba JSON Backup (API Cache)...")
    else:
        print("-> PERINGATAN: Gagal mengambil data dari API. Mencoba JSON Backup (API Cache)...")

    # 2 - Fallback ke JSON Backup (API Cache)
    data_from_json = _load_from_api_cache() # Ini membaca 'matches_backup.json'
    if data_from_json:
        print("-> SUMBER DATA: Menggunakan data dari JSON Backup (API Cache).")
        return data_from_json, "api_cache"

    # 3 - Fallback ke DB Fixture JSON (db_backup.json)
    print(f"-> STATUS: API Cache ({API_CACHE_FILE_PATH.name}) tidak ditemukan. Mencoba memuat dari DB Fixture ({DB_FIXTURE_PATH.name})...")
    data_from_fixture = _load_from_fixture_json()
    
    if data_from_fixture:
        print("-> SUMBER DATA: Menggunakan data dari DB Fixture.")
        # Simpan data yang baru di-load dari fixture ini ke dalam file cache API (matches_backup.json)
        # agar pada run berikutnya, kita tidak perlu mem-parse fixture lagi.
        _save_to_api_cache(data_from_fixture)
        return data_from_fixture, "db_fixture"
    
    # 4 - Final failure
    print("-> ERROR: Gagal mendapatkan data dari semua sumber (API, API Cache, DB Fixture).")
    return [], "error_no_source"

# --- FUNGSI UTAMA SINKRONISASI ---
def sync_database_with_apis():
    """Sinkronisasi data Match, Team, Venue dari API (atau JSON fallback) ke database."""
    print("=========================================")
    print("Memulai sinkronisasi database...")
    
    data_to_sync, source_key = _get_sync_data()
    
    if not data_to_sync:
        print("-> DB: Tidak ada data valid untuk disinkronisasi. Proses DB Write dilewati.")
        print("=========================================")
        print("Sinkronisasi database selesai (tidak ada perubahan).")
        print("=========================================\n")
        if source_key == "error_no_source":
            return "Gagal mendapatkan data dari semua sumber (API, Cache, Fixture).", "error"
        return "Tidak ada data baru untuk disinkronisasi (sumber: " + source_key + ").", source_key
    
    print(f"-> DB: Memulai pembaruan/pembuatan {len(data_to_sync)} entri database...")
    
    matches_updated_count = 0
    matches_created_count = 0
    teams_created_count = 0
    teams_updated_count = 0
    venues_created_count = 0
    venues_updated_count = 0

    # Cache lokal untuk mengurangi query DB di dalam loop
    team_cache = {team.name: team for team in Team.objects.all()}
    venue_cache = {venue.name: venue for venue in Venue.objects.all()}
    
    for match_data in data_to_sync:
        match_id_api = match_data.get('id')
        
        # Validasi data penting sebelum proses
        home_team_name = match_data.get('home_team')
        away_team_name = match_data.get('away_team')
        home_team_api_id = match_data.get('home_team_api_id')
        away_team_api_id = match_data.get('away_team_api_id')
        date_str = match_data.get('date_str')

        if not all([match_id_api, home_team_name, away_team_name, home_team_api_id, away_team_api_id, date_str]):
            print(f"-> DB: SKIPPED Match API ID {match_id_api}: Data tidak lengkap.")
            continue
        
        try:
            # --- Proses Venue ---
            venue_name_final = match_data.get('venue') or 'Unknown Stadium'
            venue_city_final = match_data.get('city') or 'Unknown City'
            
            if venue_name_final in venue_cache:
                venue = venue_cache[venue_name_final]
                if venue.city != venue_city_final:
                    venue.city = venue_city_final
                    venue.save(update_fields=['city'])
                    venues_updated_count += 1
            else:
                venue, created_venue = Venue.objects.get_or_create(
                    name=venue_name_final,
                    defaults={'city': venue_city_final}
                )
                if created_venue: venues_created_count += 1
                venue_cache[venue_name_final] = venue

            # --- Proses Tim Tuan Rumah (Home) ---
            home_league = 'liga_1' if home_team_name in LIGA_1_TEAMS else 'n/a'
            if home_team_name in team_cache:
                home_team = team_cache[home_team_name]
                if home_team.api_id != home_team_api_id or home_team.league != home_league:
                    home_team.api_id = home_team_api_id
                    home_team.league = home_league
                    home_team.save(update_fields=['api_id', 'league'])
                    teams_updated_count += 1
            else:
                home_team, created_home = Team.objects.update_or_create(
                    name=home_team_name,
                    defaults={
                        'api_id': home_team_api_id,
                        'logo_url': None, 
                        'league': home_league, 
                    }
                )
                if created_home: teams_created_count += 1
                team_cache[home_team_name] = home_team

            # --- Proses Tim Tamu (Away) ---
            away_league = 'liga_1' if away_team_name in LIGA_1_TEAMS else 'n/a'
            if away_team_name in team_cache:
                away_team = team_cache[away_team_name]
                if away_team.api_id != away_team_api_id or away_team.league != away_league:
                    away_team.api_id = away_team_api_id
                    away_team.league = away_league
                    away_team.save(update_fields=['api_id', 'league'])
                    teams_updated_count += 1
            else:
                away_team, created_away = Team.objects.update_or_create(
                    name=away_team_name,
                    defaults={
                        'api_id': away_team_api_id,
                        'logo_url': None, 
                        'league': away_league, 
                    }
                )
                if created_away: teams_created_count += 1
                team_cache[away_team_name] = away_team

            # --- Proses Pertandingan (Match) ---
            match_datetime_aware = datetime.fromisoformat(date_str)
            
            home_goals = match_data.get('home_goals')
            away_goals = match_data.get('away_goals')

            status_short = "FT" if home_goals is not None and away_goals is not None else "NS"
            status_long = "Match Finished" if status_short == "FT" else "Not Started"

            match, created = Match.objects.update_or_create(
                api_id=match_id_api,
                defaults={
                    'home_team': home_team, 
                    'away_team': away_team, 
                    'venue': venue, 
                    'date': match_datetime_aware, # Gunakan datetime object yang aware
                    'status_short': status_short,
                    'status_long': status_long,
                    'home_goals': home_goals, 
                    'away_goals': away_goals,
                }
            )
            
            if created:
                matches_created_count += 1
                # Gunakan bulk_create untuk efisiensi
                TicketPrice.objects.bulk_create([
                    TicketPrice(match=match, seat_category='VVIP', price=500000, quantity_available=50),
                    TicketPrice(match=match, seat_category='VIP', price=300000, quantity_available=200),
                    TicketPrice(match=match, seat_category='REGULAR', price=150000, quantity_available=1000),
                ], ignore_conflicts=True)
            else:
                matches_updated_count += 1

        except Exception as e:
            print(f"!!! DB: Gagal memproses Match API ID {match_id_api} ({home_team_name} vs {away_team_name}): {e}")
            continue

    print(f"-> DB: Total Pertandingan Diproses: {len(data_to_sync)}")
    print(f"-> DB: Match Baru: {matches_created_count}, Match Diperbarui: {matches_updated_count}")
    print(f"-> DB: Tim Baru: {teams_created_count}, Tim Diperbarui: {teams_updated_count}")
    print(f"-> DB: Venue Baru: {venues_created_count}, Venue Diperbarui: {venues_updated_count}")
    print("=========================================")
    print("Sinkronisasi database selesai.")
    print("=========================================\n")

    if source_key == "api_live":
        message = "Database berhasil disinkronkan dari API (Live)."
    elif source_key == "api_cache":
        message = "Database berhasil disinkronkan dari Cache API (matches_backup.json)."
    elif source_key == "db_fixture":
        message = "Database berhasil disinkronkan dari DB Fixture (db_backup.json)."
    else:
        message = "Sinkronisasi selesai."

    return message, source_key