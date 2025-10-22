import requests
from django.conf import settings
from datetime import datetime
import json
from pathlib import Path
from .models import Team, Venue, Match, TicketPrice

# --- Caching Configuration ---
# File cache akan disimpan di root proyek (BASE_DIR)
# CACHE_FILE = Path(settings.BASE_DIR) / 'match_cache.json'
# CACHE_EXPIRY = 86400 # Waktu kedaluwarsa cache dalam detik (24 jam/Harian)
# ---------------------------

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
    """Menghapus sufiks ' FC' dan menstandarisasi nama tim."""
    if name is None:
        return None
    # Menghapus ' FC' jika ada di akhir
    name = name.removesuffix(' FC').strip()
    return name

def _normalize_match_data(raw_match, source_api, logo_map={}):
    try:
        if source_api == 'api-football':
            home_name_raw = raw_match['teams']['home']['name']
            away_name_raw = raw_match['teams']['away']['name']
            
            return {
                'id': raw_match['fixture']['id'], 'date_str': raw_match['fixture']['date'],
                # Gunakan nama yang sudah dibersihkan untuk Team Model
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
                # Gunakan logo_map dengan kunci nama yang sudah dibersihkan
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
    
    # 1. Ambil data dari API-Football terlebih dahulu
    api_football_data = _fetch_api_football_matches()
    
    # 2. BANGUN logo_map LENGKAP dari API-Football (sumber logo)
    logo_map = {}
    for match in api_football_data:
        # PENTING: Gunakan nama yang sudah dibersihkan sebagai kunci map
        home_name_clean = _clean_team_name(match['teams']['home']['name'])
        away_name_clean = _clean_team_name(match['teams']['away']['name'])
        
        logo_map[home_name_clean] = match['teams']['home']['logo']
        logo_map[away_name_clean] = match['teams']['away']['logo']

    # 3. Lanjutkan Normalisasi Data API-Football
    for match in api_football_data:
        normalized = _normalize_match_data(match, 'api-football', logo_map)
        if normalized and normalized['id'] not in processed_ids:
            all_matches.append(normalized)
            processed_ids.add(normalized['id'])
    
    # 4. Lanjutkan Normalisasi Data Free-API
    for match in _fetch_freeapi_matches():
        normalized = _normalize_match_data(match, 'free-api', logo_map)
        if normalized and normalized['id'] not in processed_ids:
            all_matches.append(normalized)
            processed_ids.add(normalized['id'])

    print(f"Total {len(all_matches)} data pertandingan siap untuk disinkronkan.")
    
    PLACEHOLDER_LOGO_URL = "https://www.fotmob.com/img/league_logos/default_crests/leagues_150x150/default.png"
    
    for match_data in all_matches:
        if not all([match_data.get('home_team_api_id'), match_data.get('away_team_api_id'), match_data.get('id')]):
            continue

        venue, _ = Venue.objects.get_or_create(name=match_data.get('venue', 'N/A'), defaults={'city': match_data.get('city')})
        
        # Team Update/Create: Kunci pencarian adalah NAMA TIM yang sudah bersih
        # Karena API ID untuk tim yang sama bisa berbeda antar API.
        
        home_team, created_home = Team.objects.update_or_create(
            name=match_data.get('home_team'),
            defaults={
                'api_id': match_data.get('home_team_api_id'),
                'logo_url': match_data.get('home_logo') or PLACEHOLDER_LOGO_URL
            }
        )
        # Logika pembaruan logo placeholder tetap penting
        if not created_home and match_data.get('home_logo') and home_team.logo_url == PLACEHOLDER_LOGO_URL:
            home_team.logo_url = match_data.get('home_logo')
            home_team.save()

        away_team, created_away = Team.objects.update_or_create(
            name=match_data.get('away_team'),
            defaults={
                'api_id': match_data.get('away_team_api_id'),
                'logo_url': match_data.get('away_logo') or PLACEHOLDER_LOGO_URL
            }
        )
        if not created_away and match_data.get('away_logo') and away_team.logo_url == PLACEHOLDER_LOGO_URL:
            away_team.logo_url = match_data.get('away_logo')
            away_team.save()

        # ... (Logika Match update/create tetap sama)
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