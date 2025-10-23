import requests
from django.conf import settings
from datetime import datetime
from django.core.cache import cache
from .models import Team, Venue, Match, TicketPrice
from django.utils import timezone

CACHE_KEY_SYNC = 'full_match_sync_data'
CACHE_TIMEOUT = 60 * 60 * 24

TEAM_NAME_STANDARDIZATION = {
    "arema": "Arema FC",
    "arema fc": "Arema FC",
    "bali united": "Bali United FC",
    "bali united fc": "Bali United FC",
    "bhayangkara": "Bhayangkara Presisi Lampung FC",
    "bhayangkara fc": "Bhayangkara Presisi Lampung FC",
    "bhayangkara presisi indonesia": "Bhayangkara Presisi Lampung FC",
    "bhayangkara presisi indonesia fc": "Bhayangkara Presisi Lampung FC",
    "pusamania borneo": "Borneo Samarinda FC",
    "borneo samarinda": "Borneo Samarinda FC",
    "dewa united": "Dewa United Banten FC",
    "dewa united fc": "Dewa United Banten FC",
    "madura united": "Madura United FC",
    "persepam madura utd": "Madura United FC",
    "malut united": "Malut United FC",
    "persebaya surabaya": "Persebaya Surabaya",
    "persib bandung": "Persib Bandung",
    "persija jakarta": "Persija Jakarta",
    "persijap jepara": "Persijap Jepara",
    "persik": "Persik Kediri",
    "persik kediri": "Persik Kediri",
    "persis solo": "Persis Solo",
    "persita": "Persita Tangerang",
    "psbs biak numfor": "PSBS Biak Numfor",
    "psim yogyakarta": "PSIM Yogyakarta",
    "psm makassar": "PSM Makassar",
    "semen padang": "Semen Padang FC",
    "semen padang fc": "Semen Padang FC",
    
    # Tim tidak bermain di liga super 2025
    "psis semarang": "PSIS Semarang",
    "pss sleman": "PSS Sleman",
    "cilegon united": "Cilegon United",
    "ps tira": "PS TIRA",
    "barito putera": "PS Barito Putera",
}

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
        data = response.json().get('response', {}).get('matches', [])
        print(f"-> API: Berhasil mengambil {len(data)} pertandingan.")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"Error fetching data from FreeAPI: {e}")
        if e.response.status_code == 429:
            print("Error 429: Rate limit tercapai. Menggunakan data cache yang sudah ada.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from FreeAPI: {e}")
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
        
        return {
            'id': raw_match['id'], 
            'date_str': raw_match['status']['utcTime'],
            'home_team': home_team_name_clean, 
            'home_goals': raw_match['home']['score'], 
            'away_goals': raw_match['away']['score'],
            'venue': 'N/A', 'city': 'N/A', 
            'home_team_api_id': raw_match['home']['id'], 
            'away_team_api_id': raw_match['away']['id'],
        }
    except (KeyError, TypeError, AttributeError) as e:
        print(f"Error normalizing match data: {e}")
        return None

def sync_database_with_apis():
    print("\n=========================================")
    print("Memulai sinkronisasi database dengan API/Cache...")
    
    cached_matches = cache.get(CACHE_KEY_SYNC)
    
    if not cached_matches:
        print("-> STATUS: Cache Miss. Mengambil data dari API...")
        # ==========================================================
        # BLOK CACHE MISS (Mengambil dari API)
        # ==========================================================
        raw_free_api_data = _fetch_freeapi_matches()
        all_matches = []
        processed_ids = set()
        
        for match in raw_free_api_data:
            normalized = _normalize_match_data(match)
            if normalized and normalized['id'] not in processed_ids:
                all_matches.append(normalized)
                processed_ids.add(normalized['id'])

        if all_matches:
            cache.set(CACHE_KEY_SYNC, all_matches, timeout=CACHE_TIMEOUT)
            print(f"-> CACHE: Data {len(all_matches)} pertandingan BERHASIL DISIMPAN ke cache.")
            data_to_sync = all_matches
        else:
            print("Sinkronisasi dihentikan: Cache kosong dan API gagal diakses.")
            return 
    else:
        # ==========================================================
        # BLOK CACHE HIT (Mengambil dari Cache)
        # ==========================================================
        print(f"-> STATUS: Cache Hit. Menggunakan data {len(cached_matches)} pertandingan dari CACHE.")
        data_to_sync = cached_matches
    
    
    # Proses Sync ke DB (menggunakan data_to_sync)
    print("-> DB: Memulai pembaruan/pembuatan entri database...")
    for match_data in data_to_sync:
        if not all([match_data.get('home_team_api_id'), match_data.get('away_team_api_id'), match_data.get('id')]):
            continue

        home_team_name = match_data.get('home_team')
        away_team_name = match_data.get('away_team')
        
        if not home_team_name or not away_team_name:
            continue

        venue, _ = Venue.objects.get_or_create(name=match_data.get('venue', 'Unknown Stadium'), defaults={'city': match_data.get('city', 'Unknown City')})
        
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

    print("=========================================")
    print("Sinkronisasi database selesai.")
    print("=========================================\n")