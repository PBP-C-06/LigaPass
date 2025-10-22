from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.core.cache import cache
import requests
from django.conf import settings
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView

from .models import Team, Match, TicketPrice
from .forms import TeamForm
from .services import sync_database_with_apis

# --- AUTHENTICATION & HELPER FUNCTIONS ---

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'admin'

def _get_cleaned_messages(request):
    """Mengubah objek pesan Django menjadi daftar dictionary yang aman untuk JSON (FIX: TypeError)."""
    django_messages = messages.get_messages(request)
    message_list = []
    for message in django_messages:
        message_list.append({
            'message': str(message), 
            'tags': message.tags  
        })
    return message_list

def get_match_status(match_time):
    now = timezone.now()
    if match_time > now:
        return 'Upcoming'
    elif match_time <= now and (now - match_time) < timedelta(hours=2.5):
        return 'Ongoing'
    else:
        return 'Past'

# --- FUNCTION-BASED VIEWS ---

def match_calendar_view(request):
    queryset = Match.objects.select_related('home_team', 'away_team', 'venue').order_by('date')
    
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(home_team__name__icontains=search_query) |
            Q(away_team__name__icontains=search_query)
        )

    grouped_matches = {'Upcoming': [], 'Ongoing': [], 'Past': []}
    
    for match in queryset:
        status = get_match_status(match.date)
        match.status_key = status
        grouped_matches[status].append(match)

    context = {
        'grouped_matches': grouped_matches,
        'messages_json': _get_cleaned_messages(request),
    }
    return render(request, 'matches/calendar.html', context)

def match_details_view(request, match_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team', 'venue'), id=match_id)
    
    status = get_match_status(match.date)
    ticket_prices = match.ticket_prices.all().order_by('price')
    match.status_key = status

    context = {
        'match': match,
        'ticket_prices': ticket_prices,
        'messages_json': _get_cleaned_messages(request),
    }
    
    return render(request, 'matches/details.html', context)

@user_passes_test(is_admin)
def update_matches_view(request):
    print("Memicu pembaruan database dari API...")
    sync_database_with_apis()
    messages.success(request, 'Database pertandingan berhasil diperbarui dari API.')
    return redirect('matches:calendar') 

def live_score_api(request, match_api_id):
    cache_key = f"live_score_{match_api_id}"
    cached_data = cache.get(cache_key)

    if cached_data:
        print(f"Mengambil live score untuk match {match_api_id} dari CACHE.")
        return JsonResponse(cached_data)

    print(f"Mengambil live score untuk match {match_api_id} dari API.")
    
    url = f"https://v3.football.api-sports.io/fixtures?id={match_api_id}"
    headers = {
        'x-rapidapi-key': settings.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        api_data = response.json().get('response', [])
        
        if not api_data:
            return JsonResponse({'error': 'Match not found in API'}, status=404)

        match_data = api_data[0]
        live_data = {
            'home_goals': match_data['goals']['home'],
            'away_goals': match_data['goals']['away'],
            'status_short': match_data['fixture']['status']['short'],
            'status_long': match_data['fixture']['status']['long'],
            'elapsed': match_data['fixture']['status']['elapsed'],
        }
        
        cache.set(cache_key, live_data, timeout=55)
        return JsonResponse(live_data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# --- CLASS-BASED VIEWS (CRUD Tim) ---

class TeamListView(AdminRequiredMixin, ListView):
    model = Team
    template_name = 'matches/manage/team_list.html'
    context_object_name = 'teams'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        return context

class TeamCreateView(AdminRequiredMixin, CreateView):
    model = Team
    form_class = TeamForm
    template_name = 'matches/manage/team_form.html'
    success_url = reverse_lazy('matches:manage_teams')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Tim "{self.object.name}" berhasil ditambahkan.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        return context

class TeamUpdateView(AdminRequiredMixin, UpdateView):
    model = Team
    form_class = TeamForm
    template_name = 'matches/manage/team_form.html'
    success_url = reverse_lazy('matches:manage_teams')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Tim "{self.object.name}" berhasil diperbarui.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        return context
class TeamDeleteView(AdminRequiredMixin, DeleteView):
    model = Team
    template_name = 'matches/manage/team_confirm_delete.html'
    success_url = reverse_lazy('matches:manage_teams')
    
    def form_valid(self, form):
        team_name = self.object.name
        messages.success(self.request, f'Tim "{team_name}" berhasil dihapus.')
        return super().form_valid(form)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        return context