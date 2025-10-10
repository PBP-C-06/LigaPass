from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta
from .services import fetch_upcoming_matches

# Fungsi pembantu untuk mengelompokkan status pertandingan
def get_match_status(match_time):
    now = timezone.now()
    
    # Jika waktu pertandingan di masa depan
    if match_time > now:
        return 'Upcoming'
    
    # Jika waktu pertandingan telah dimulai (misalnya, dalam 2 jam terakhir)
    # Ini adalah perkiraan, status 'Live' biasanya didapat dari API
    elif match_time <= now and (now - match_time) < timedelta(hours=2):
        return 'Ongoing'
        
    # Selain itu, pertandingan dianggap sudah selesai
    else:
        return 'Past'

def match_calendar_view(request):
    api_matches = fetch_upcoming_matches()
    
    # Inisialisasi pengelompokan seperti yang dijelaskan di README
    grouped_matches = {
        'Upcoming': [],
        'Ongoing': [],
        'Past': [],
    }
    
    for match_data in api_matches:
        try:
            # Mengonversi waktu pertandingan dari string API ke objek datetime dengan timezone
            # Asumsi format API adalah ISO 8601
            match_datetime_str = match_data['fixture']['date']
            match_datetime = datetime.fromisoformat(match_datetime_str.replace('Z', '+00:00'))
            
            status = get_match_status(match_datetime)
            
            match_detail = {
                'id': match_data['fixture']['id'],
                'date': match_datetime,
                'status': status,
                'home_team': match_data['teams']['home']['name'],
                'home_logo': match_data['teams']['home']['logo'],
                'away_team': match_data['teams']['away']['name'],
                'away_logo': match_data['teams']['away']['logo'],
                'venue': match_data['fixture']['venue']['name'],
                # Masih bisa menambahkan data lain yang diperlukan (mungkin nanti)
            }
            
            # Kelompokkan pertandingan
            grouped_matches[status].append(match_detail)
            
        except Exception as e:
            # Log error untuk debugging
            print(f"Error processing match data: {e}")
            continue

    context = {
        'grouped_matches': grouped_matches,
    }
    
    return render(request, 'matches/calendar.html', context)