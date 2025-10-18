# matches/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test

from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import Team, Match, TicketPrice
from .forms import TeamForm
from .services import sync_database_with_apis

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

# Fungsi pembantu untuk mengelompokkan status pertandingan
def get_match_status(match_time):
    now = timezone.now()
    if match_time > now:
        return 'Upcoming'
    elif match_time <= now and (now - match_time) < timedelta(hours=2):
        return 'Ongoing'
    else:
        return 'Past'

def match_calendar_view(request):
    queryset = Match.objects.select_related('home_team', 'away_team', 'venue').order_by('date')
    
    # Handle search
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(home_team__name__icontains=search_query) |
            Q(away_team__name__icontains=search_query)
        )

    # Inisialisasi pengelompokan seperti yang dijelaskan di README
    grouped_matches = {
        'Upcoming': [],
        'Ongoing': [],
        'Past': [],
    }
    
    for match in queryset:
        status = get_match_status(match.date)
        match.status_key = status
        grouped_matches[status].append(match)

    context = {
        'grouped_matches': grouped_matches,
    }
    
    return render(request, 'matches/calendar.html', context)

def match_detail_view(request, match_api_id):
    match = get_object_or_404(Match.objects.select_related('home_team', 'away_team', 'venue'), api_id=match_api_id)
    
    status = get_match_status(match.date)
    ticket_prices = match.ticket_prices.all().order_by('price')
    match.status_key = status

    context = {
        'match': match,
        'ticket_prices': ticket_prices,
    }
    
    return render(request, 'matches/details.html', context)

def update_matches_view(request):
    # --- PERBAIKAN: Pengecekan izin manual ---
    if not (request.user.is_authenticated and request.user.role == 'admin'):
        # Jika bukan admin, tampilkan halaman error "Akses Ditolak"
        return render(request, 'matches/permission_denied.html', status=403)
    
    # Kode di bawah ini hanya akan berjalan jika pengguna adalah admin
    print("Memicu pembaruan database dari API...")
    sync_database_with_apis()
    messages.success(request, 'Database pertandingan berhasil diperbarui dari API.')
    return redirect('matches:calendar')

# Mixin untuk membatasi akses hanya untuk Admin
class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
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