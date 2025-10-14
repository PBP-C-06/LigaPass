from django.shortcuts import render
from django.utils import timezone
from datetime import datetime, timedelta

from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from matches.models import Team
from matches.forms import TeamForm
from matches.services import fetch_upcoming_matches

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

def match_detail_view(request, match_api_id):
    api_matches = fetch_upcoming_matches()
    match_data = next((match for match in api_matches if match['fixture']['id'] == match_api_id), None)
    
    if not match_data:
        return render(request, 'matches/not_found.html', {'match_id': match_api_id})

    match_datetime = datetime.fromisoformat(match_data['fixture']['date'].replace('Z', '+00:00'))
    status = get_match_status(match_datetime)

    # --- BAGIAN KRITIS ADA DI SINI ---
    # Pastikan semua key ini sama persis
    context = {
        'match': {
            'id': match_data['fixture']['id'],
            'date': match_datetime,
            'home_team': match_data['teams']['home']['name'],
            'home_logo': match_data['teams']['home']['logo'],
            'away_team': match_data['teams']['away']['name'],      # <-- Pastikan key ini ada
            'away_logo': match_data['teams']['away']['logo'],      # <-- Pastikan key ini ada
            'venue': match_data['fixture']['venue']['name'],
            'city': match_data['fixture']['venue']['city'],
            'status_long': match_data['fixture']['status']['long'],
            'home_goals': match_data['goals']['home'],             # <-- Pastikan key ini ada
            'away_goals': match_data['goals']['away'],
            'status_key': status,
        }
    }
    
    return render(request, 'matches/details.html', context)

# Mixin untuk membatasi akses hanya untuk Admin
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        # Asumsi role 'admin' ada di model User Anda
        return self.request.user.is_authenticated and self.request.user.role == 'admin'

# Read (List)
class TeamListView(AdminRequiredMixin, ListView):
    model = Team
    template_name = 'matches/manage/team_list.html'
    context_object_name = 'teams'

# Create
class TeamCreateView(AdminRequiredMixin, CreateView):
    model = Team
    form_class = TeamForm
    template_name = 'matches/manage/team_form.html'
    success_url = reverse_lazy('matches:manage_teams')

# Update
class TeamUpdateView(AdminRequiredMixin, UpdateView):
    model = Team
    form_class = TeamForm
    template_name = 'matches/manage/team_form.html'
    success_url = reverse_lazy('matches:manage_teams')

# Delete
class TeamDeleteView(AdminRequiredMixin, DeleteView):
    model = Team
    template_name = 'matches/manage/team_confirm_delete.html'
    success_url = reverse_lazy('matches:manage_teams')