# matches/services.py

import requests
from django.conf import settings
from datetime import datetime
import json
from pathlib import Path
from .models import Team, Venue, Match, TicketPrice

# --- Caching Configuration ---
# File cache akan disimpan di root proyek (BASE_DIR)
CACHE_FILE = Path(settings.BASE_DIR) / 'match_cache.json'
CACHE_EXPIRY = 86400 # Waktu kedaluwarsa cache dalam detik (24 jam/Harian)
# ---------------------------

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
    # Ambil nilai standardisasi (VALUENYA) dari dictionary di atas
    "Arema FC", "Bali United FC", "Bhayangkara Presisi Lampung FC", 
    "Borneo Samarinda FC", "Dewa United Banten FC", "Madura United FC", 
    "Malut United FC", "Persebaya Surabaya", "Persib Bandung", 
    "Persija Jakarta", "Persik Kediri", "Persis Solo", 
    "Persita Tangerang", "PSBS Biak Numfor", "PSIM Yogyakarta", 
    "PSM Makassar", "Semen Padang FC", "Persijap Jepara"
}
# --------------------------------------------------------------------------

def _fetch_api_football_matches(league_id=274, season=2023):
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    params = {'league': league_id, 'season': season, 'timezone': 'Asia/Jakarta'}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        print(f"Berhasil mengambil {len(response.json().get('response', []))} pertandingan dari API-Football.")
        return response.json().get('response', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API-Football: {e}")
        return []

def _fetch_freeapi_matches(league_id=8983):
    url = "https://free-api-live-football-data.p.rapidapi.com/football-get-all-matches-by-league"
    headers = {
        "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
        "x-rapidapi-key": settings.RAPID_API_KEY
    }
    params = {"leagueid": league_id}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get('response', {}).get('matches', [])
        print(f"Berhasil mengambil {len(data)} pertandingan dari Free-API.")
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from FreeAPI: {e}")
        return []

def _clean_team_name(name):
    """Menstandardisasi nama tim berdasarkan dictionary TEAM_NAME_STANDARDIZATION."""
    if name is None:
        return None
    # Konversi ke lowercase dan hapus spasi awal/akhir
    clean_key = name.lower().strip()
    
    # Ambil nama standar, jika tidak ada di mapping, gunakan nama aslinya (title case)
    return TEAM_NAME_STANDARDIZATION.get(clean_key, name.strip().title())

def _normalize_match_data(raw_match, source_api, logo_map={}):
    try:
        if source_api == 'api-football':
            home_name_raw = raw_match['teams']['home']['name']
            away_name_raw = raw_match['teams']['away']['name']
            
            return {
                'id': raw_match['fixture']['id'], 'date_str': raw_match['fixture']['date'],
                'home_team': _clean_team_name(home_name_raw), 
                'home_logo': raw_match['teams']['home']['logo'],
                'away_team': _clean_team_name(away_name_raw), 
                'away_logo': raw_match['teams']['away']['logo'],
                'home_goals': raw_match['goals']['home'], 'away_goals': raw_match['goals']['away'],
                'venue': raw_match['fixture']['venue']['name'], 'city': raw_match['fixture']['venue']['city'],
                'home_team_api_id': raw_match['teams']['home']['id'], 'away_team_api_id': raw_match['teams']['away']['id'],
            }
        elif source_api == 'free-api':
            home_team_name_raw = raw_match['home']['name']
            away_team_name_raw = raw_match['away']['name']
            
            home_team_name_clean = _clean_team_name(home_team_name_raw)
            away_team_name_clean = _clean_team_name(away_team_name_raw)
            
            return {
                'id': raw_match['id'], 'date_str': raw_match['status']['utcTime'],
                'home_team': home_team_name_clean, 
                'home_logo': logo_map.get(home_team_name_clean),
                'away_team': away_team_name_clean, 
                'away_logo': logo_map.get(away_team_name_clean),
                'home_goals': raw_match['home']['score'], 'away_goals': raw_match['away']['score'],
                'venue': 'N/A', 'city': 'N/A',
                'home_team_api_id': raw_match['home']['id'], 'away_team_api_id': raw_match['away']['id'],
            }
    except (KeyError, TypeError):
        return None
    return None

def sync_database_with_apis():
    print("Memulai sinkronisasi database dengan API...")
    all_matches, processed_ids = [], set()
    
    api_football_data = _fetch_api_football_matches()
    
    # 2. BANGUN logo_map LENGKAP dari API-Football (sumber logo utama)
    logo_map = {}
    for match in api_football_data:
        home_name_clean = _clean_team_name(match['teams']['home']['name'])
        away_name_clean = _clean_team_name(match['teams']['away']['name'])
        
        logo_map[home_name_clean] = match['teams']['home']['logo']
        logo_map[away_name_clean] = match['teams']['away']['logo']

    # 3. Kumpulkan dan normalisasi semua data pertandingan
    for match in api_football_data:
        normalized = _normalize_match_data(match, 'api-football', logo_map)
        if normalized and normalized['id'] not in processed_ids:
            all_matches.append(normalized)
            processed_ids.add(normalized['id'])
    
    for match in _fetch_freeapi_matches():
        normalized = _normalize_match_data(match, 'free-api', logo_map)
        if normalized and normalized['id'] not in processed_ids:
            all_matches.append(normalized)
            processed_ids.add(normalized['id'])

    print(f"Total {len(all_matches)} data pertandingan siap untuk disinkronkan.")
    
    for match_data in all_matches:
        if not all([match_data.get('home_team_api_id'), match_data.get('away_team_api_id'), match_data.get('id')]):
            continue

        venue, _ = Venue.objects.get_or_create(name=match_data.get('venue', 'N/A'), defaults={'city': match_data.get('city')})
        
        # --- Update/Create Home Team ---
        home_team_name = match_data.get('home_team') # Nama standar tim Home
        
        home_league = 'liga_1' if home_team_name in LIGA_1_TEAMS else 'liga_2'
        
        home_team, created_home = Team.objects.update_or_create(
            name=home_team_name,
            defaults={
                'api_id': match_data.get('home_team_api_id'),
                'logo_url': match_data.get('home_logo') or None,
                'league': home_league, # <= FIELD BARU
            }
        )
        
        # Jaga logo yang sudah disetel admin
        if not created_home and match_data.get('home_logo') and home_team.logo_url is None:
            home_team.logo_url = match_data.get('home_logo')
            home_team.save()

        # --- Update/Create Away Team ---
        away_team_name = match_data.get('away_team') # Nama standar tim Away
        
        away_league = 'liga_1' if away_team_name in LIGA_1_TEAMS else 'liga_2'
        
        away_team, created_away = Team.objects.update_or_create(
            name=away_team_name,
            defaults={
                'api_id': match_data.get('away_team_api_id'),
                'logo_url': match_data.get('away_logo') or None,
                'league': away_league, # <= FIELD BARU
            }
        )
        if not created_away and match_data.get('away_logo') and away_team.logo_url is None:
            away_team.logo_url = match_data.get('away_logo')
            away_team.save()

        # --- Update/Create Match ---
        match_datetime = datetime.fromisoformat(match_data['date_str'].replace('Z', '+00:00'))
        
        match, created = Match.objects.update_or_create(
            api_id=match_data.get('id'),
            defaults={
                'home_team': home_team, 'away_team': away_team, 'venue': venue, 'date': match_datetime,
                'status_short': "FT" if match_data.get('home_goals') is not None else "NS",
                'status_long': "Match Finished" if match_data.get('home_goals') is not None else "Not Started",
                'home_goals': match_data.get('home_goals'), 'away_goals': match_data.get('away_goals'),
            }
        )
        if created:
            TicketPrice.objects.create(match=match, seat_category='VVIP', price=500000, quantity_available=50)
            TicketPrice.objects.create(match=match, seat_category='VIP', price=300000, quantity_available=200)
            TicketPrice.objects.create(match=match, seat_category='REGULAR', price=150000, quantity_available=1000)

    print("Sinkronisasi database selesai.")