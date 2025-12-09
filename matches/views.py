from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Min
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponse
from django.core.cache import cache
import requests
from django.conf import settings
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from datetime import datetime as dt
from django.db.models.functions import TruncDate
from django.contrib.auth.decorators import user_passes_test
from datetime import datetime
from datetime import time
from reviews.models import Review
from bookings.models import Ticket
from django.db.models import Avg
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_GET
from django.utils.text import slugify
from django.templatetags.static import static
from django.contrib.staticfiles import finders
import mimetypes
import json


from .models import Team, Match, Venue, TicketPrice
from .forms import TeamForm, MatchForm, TicketPriceFormSet
from .services import sync_database_with_apis
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'admin'

def _get_cleaned_messages(request):
    django_messages = messages.get_messages(request)
    message_list = []
    for message in django_messages:
        message_list.append({
            'message': str(message),
            'tags': message.tags
        })
    return message_list


def _serialize_team(team, request=None):
    proxy_logo = None
    if request:
        proxy_logo = request.build_absolute_uri(
            reverse('matches:flutter_team_logo_proxy', args=[team.id])
        )
    return {
        'id': str(team.id),
        'name': team.name,
        'league': team.league,
        'league_label': team.get_league_display(),
        'logo_url': team.logo_url or '',
        'logo_proxy_url': proxy_logo,
    }


def _serialize_venue(venue, request=None):
    image_url = None
    if request:
        image_url = request.build_absolute_uri(
            reverse('matches:flutter_venue_image_proxy', args=[venue.id])
        )
    return {
        'id': str(venue.id),
        'name': venue.name,
        'city': venue.city,
        'image_url': image_url,
    }

def get_match_status(match_time):
    now = timezone.now()
    if match_time > now:
        return 'Upcoming'
    elif match_time <= now and (now - match_time) < timedelta(hours=2.5):
        return 'Ongoing'
    else:
        return 'Finished'

def _serialize_match(match, request=None):
    proxy_home_logo = None
    proxy_away_logo = None
    if request:
        proxy_home_logo = request.build_absolute_uri(
            reverse('matches:flutter_team_logo_proxy', args=[match.home_team.id])
        )
        proxy_away_logo = request.build_absolute_uri(
            reverse('matches:flutter_team_logo_proxy', args=[match.away_team.id])
        )

    return {
        'id': str(match.id),
        'home_team_name': match.home_team.name,
        'home_logo_url': match.home_team.display_logo_url,
        'home_logo_proxy_url': proxy_home_logo,
        'home_team_id': str(match.home_team.id),
        'away_team_name': match.away_team.name,
        'away_logo_url': match.away_team.display_logo_url,
        'away_logo_proxy_url': proxy_away_logo,
        'away_team_id': str(match.away_team.id),
        'date': match.date.strftime('%d %b %Y @ %H:%M WIB'),
        'date_iso': match.date.isoformat(),
        'status_key': get_match_status(match.date),
        'status_short': match.status_short,
        'status_long': match.status_long,
        'home_goals': match.home_goals if match.home_goals is not None else 0,
        'away_goals': match.away_goals if match.away_goals is not None else 0,
        'details_url': reverse('matches:details', args=[match.id]),
        'venue_name': match.venue.name if match.venue else 'N/A',
        'venue_city': match.venue.city if match.venue else 'N/A',
        'venue_id': str(match.venue.id) if match.venue else None,
        'edit_url': reverse('matches:edit_match', args=[match.id]),
        'delete_url': reverse('matches:delete_match', args=[match.id])
    }


def match_calendar_view(request):
    search_query = request.GET.get('q', '')

    context = {
        'messages_json': _get_cleaned_messages(request),
        'search_query': search_query,
        'venues': Venue.objects.all().order_by('name'),
        'teams': Team.objects.all().order_by('name')
    }
    return render(request, 'matches/calendar.html', context)

def api_match_list(request):
    queryset = Match.objects.select_related('home_team', 'away_team', 'venue').order_by('date')

    search_query = request.GET.get('q', '')
    date_start_filter = request.GET.get('date_start', '')
    date_end_filter = request.GET.get('date_end', '')
    venue_filter = request.GET.get('venue', '')
    status_filter = request.GET.get('status', '')

    if search_query:
        queryset = queryset.filter(
            Q(home_team__name__icontains=search_query) |
            Q(away_team__name__icontains=search_query)
        )

    if venue_filter:
        queryset = queryset.filter(venue__id=venue_filter)

    if date_start_filter:
        try:
            start_date = dt.strptime(date_start_filter, '%Y-%m-%d').date()
            start_datetime = timezone.make_aware(dt.combine(start_date, time.min))

            if date_end_filter:
                end_date = dt.strptime(date_end_filter, '%Y-%m-%d').date()
                end_datetime = timezone.make_aware(dt.combine(end_date, time.max))
                queryset = queryset.filter(date__range=(start_datetime, end_datetime))
            else:
                end_datetime = timezone.make_aware(dt.combine(start_date, time.max))
                queryset = queryset.filter(date__range=(start_datetime, end_datetime))

        except ValueError:
            pass

    now = timezone.now()
    q_filter_status = Q()
    status_filter = request.GET.get('status', '')

    allowed_statuses = []
    if status_filter:
        allowed_statuses = [s.strip() for s in status_filter.split(',') if s.strip()]

    if allowed_statuses:
        if 'Upcoming' in allowed_statuses:
            q_filter_status |= Q(date__gt=now)
        if 'Ongoing' in allowed_statuses:
            q_filter_status |= Q(date__lte=now, date__gt=now - timedelta(hours=2.5))
        if 'Finished' in allowed_statuses:
            q_filter_status |= Q(date__lte=now - timedelta(hours=2.5))

        if q_filter_status != Q():
             queryset = queryset.filter(q_filter_status)
        else:
             pass
    else:
        pass


    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
        if per_page not in [5, 10, 25, 50]:
            per_page = 10
    except ValueError:
        per_page = 10

    paginator = Paginator(queryset, per_page)
    try:
        matches_page = paginator.page(page)
    except PageNotAnInteger:
        matches_page = paginator.page(1)
    except EmptyPage:
        matches_page = paginator.page(paginator.num_pages)

    matches_list = []

    for match in matches_page.object_list:
        matches_list.append(_serialize_match(match, request))

    return JsonResponse({
        'matches': matches_list,
        'search_query': search_query,
        'pagination': {
            'total_pages': paginator.num_pages,
            'current_page': matches_page.number,
            'has_previous': matches_page.has_previous(),
            'has_next': matches_page.has_next(),
            'total_items': paginator.count,
            'per_page': per_page,
            'page_range': list(paginator.get_elided_page_range(number=matches_page.number, on_each_side=1, on_ends=1)),
        }
    })


def _build_absolute_static_uri(request, path):
    return request.build_absolute_uri(static(path))


def _venue_image_url(request, venue):
    slug = slugify(f"{venue.name} {venue.city}")
    filename = f"{slug}.png"
    path = f"venues/{filename}"
    if finders.find(path):
        return _build_absolute_static_uri(request, path)
    return _build_absolute_static_uri(request, "images/thumbnail_placeholder.png")


def _serve_static_file(path, fallback_path="images/thumbnail_placeholder.png"):
    candidate = finders.find(path) or finders.find(fallback_path) or finders.find("images/thumbnail_placeholder.png")
    if not candidate:
        return HttpResponse(status=404)

    content_type, _ = mimetypes.guess_type(candidate)
    file = open(candidate, "rb")
    return FileResponse(file, content_type=content_type or "application/octet-stream")


def _proxy_external_image(url):
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "application/octet-stream")
        return HttpResponse(resp.content, content_type=content_type)
    except Exception:
        return None


@require_GET
def flutter_team_logos(request):
    teams = Team.objects.all().order_by('name')
    data = []

    for team in teams:
        logo_url = request.build_absolute_uri(reverse('matches:flutter_team_logo_proxy', args=[team.id]))
        data.append({
            'id': str(team.id),
            'name': team.name,
            'league': team.league,
            'league_label': team.get_league_display(),
            'logo_url': logo_url,
        })

    return JsonResponse({'teams': data})


@require_GET
def flutter_venue_images(request):
    venues = Venue.objects.all().order_by('name')
    data = []

    for venue in venues:
        data.append({
            'id': str(venue.id),
            'name': venue.name,
            'city': venue.city,
            'image_url': request.build_absolute_uri(reverse('matches:flutter_venue_image_proxy', args=[venue.id])),
        })

    return JsonResponse({'venues': data})


@require_GET
def flutter_team_logo_proxy(request, team_id):
    team = get_object_or_404(Team, id=team_id)

    if team.logo_url:
        proxied = _proxy_external_image(team.logo_url)
        if proxied:
            return proxied

    filename = team.static_logo_filename
    path = f"matches/images/team_logos/{team.league}/{filename}"
    return _serve_static_file(path)


@require_GET
def flutter_venue_image_proxy(request, venue_id):
    venue = get_object_or_404(Venue, id=venue_id)
    slug = slugify(f"{venue.name} {venue.city}")
    filename = f"{slug}.png"
    path = f"venues/{filename}"
    return _serve_static_file(path)


def _require_admin(request):
    if not is_admin(request.user):
        return JsonResponse({'detail': 'Unauthorized'}, status=403)
    return None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def admin_team_list_api(request):
    if (resp := _require_admin(request)) is not None:
        return resp

    if request.method == "GET":
        teams = Team.objects.all().order_by('name')
        data = [_serialize_team(t, request) for t in teams]
        return JsonResponse({'teams': data})

    payload = json.loads(request.body.decode() or '{}')
    name = payload.get('name', '')
    league = payload.get('league', 'n/a')
    logo_url = payload.get('logo_url') or ''
    team = Team.objects.create(name=name, league=league, logo_url=logo_url)
    return JsonResponse({'team': _serialize_team(team, request)})


@csrf_exempt
@require_http_methods(["POST"])
def admin_team_detail_api(request, team_id):
    if (resp := _require_admin(request)) is not None:
        return resp
    payload = json.loads(request.body.decode() or '{}')
    action = payload.get('action')
    team = Team.objects.filter(id=team_id).first()
    if not team:
        return JsonResponse({'errors': 'Tim tidak ditemukan'}, status=404)

    if action == 'delete':
        team.delete()
        return JsonResponse({'success': True})

    team.name = payload.get('name', team.name)
    team.league = payload.get('league', team.league)
    team.logo_url = payload.get('logo_url', team.logo_url)
    team.save()
    return JsonResponse({'team': _serialize_team(team, request)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def admin_venue_list_api(request):
    if (resp := _require_admin(request)) is not None:
        return resp

    if request.method == "GET":
        venues = Venue.objects.all().order_by('name')
        data = [_serialize_venue(v, request) for v in venues]
        return JsonResponse({'venues': data})

    payload = json.loads(request.body.decode() or '{}')
    venue = Venue.objects.create(
        name=payload.get('name', ''),
        city=payload.get('city'),
    )
    return JsonResponse({'venue': _serialize_venue(venue, request)})


@csrf_exempt
@require_http_methods(["POST"])
def admin_venue_detail_api(request, venue_id):
    if (resp := _require_admin(request)) is not None:
        return resp

    payload = json.loads(request.body.decode() or '{}')
    action = payload.get('action')
    venue = Venue.objects.filter(id=venue_id).first()
    if not venue:
        return JsonResponse({'errors': 'Venue tidak ditemukan'}, status=404)

    if action == 'delete':
        venue.delete()
        return JsonResponse({'success': True})

    venue.name = payload.get('name', venue.name)
    venue.city = payload.get('city', venue.city)
    venue.save()
    return JsonResponse({'venue': _serialize_venue(venue, request)})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def admin_match_list_api(request):
    if (resp := _require_admin(request)) is not None:
        return resp

    if request.method == "GET":
        matches = Match.objects.select_related('home_team', 'away_team', 'venue').order_by('date')
        data = [_serialize_match(m, request) for m in matches]
        return JsonResponse({'matches': data})

    payload = json.loads(request.body.decode() or '{}')
    try:
        home_team = Team.objects.get(id=payload.get('home_team'))
        away_team = Team.objects.get(id=payload.get('away_team'))
    except Team.DoesNotExist:
        return JsonResponse({'errors': 'Tim tidak ditemukan'}, status=400)

    venue = None
    venue_id = payload.get('venue')
    if venue_id:
        venue = Venue.objects.filter(id=venue_id).first()

    date_str = payload.get('date')
    try:
        date = datetime.fromisoformat(date_str)
    except Exception:
        return JsonResponse({'errors': 'Format tanggal tidak valid'}, status=400)

    match = Match.objects.create(
        home_team=home_team,
        away_team=away_team,
        venue=venue,
        date=date,
        home_goals=payload.get('home_goals'),
        away_goals=payload.get('away_goals'),
        status_short=payload.get('status_short', 'NS') or 'NS',
        status_long=payload.get('status_long', 'Not Started') or 'Not Started',
    )
    return JsonResponse({'match': _serialize_match(match, request)})


@csrf_exempt
@require_http_methods(["POST"])
def admin_match_detail_api(request, match_id):
    if (resp := _require_admin(request)) is not None:
        return resp

    payload = json.loads(request.body.decode() or '{}')
    action = payload.get('action')
    match = Match.objects.filter(id=match_id).first()
    if not match:
        return JsonResponse({'errors': 'Pertandingan tidak ditemukan'}, status=404)

    if action == 'delete':
        match.delete()
        return JsonResponse({'success': True})

    if 'home_team' in payload:
        match.home_team = get_object_or_404(Team, id=payload['home_team'])
    if 'away_team' in payload:
        match.away_team = get_object_or_404(Team, id=payload['away_team'])
    if 'venue' in payload:
        venue_id = payload.get('venue')
        match.venue = Venue.objects.filter(id=venue_id).first() if venue_id else None
    if 'date' in payload:
        try:
            match.date = datetime.fromisoformat(payload['date'])
        except Exception:
            return JsonResponse({'errors': 'Format tanggal tidak valid'}, status=400)
    if 'home_goals' in payload:
        match.home_goals = payload.get('home_goals')
    if 'away_goals' in payload:
        match.away_goals = payload.get('away_goals')
    if 'status_short' in payload:
        match.status_short = payload.get('status_short') or match.status_short
    if 'status_long' in payload:
        match.status_long = payload.get('status_long') or match.status_long

    match.save()
    return JsonResponse({'match': _serialize_match(match, request)})


def match_details_view(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team', 'venue'),
        id=match_id
    )

    status = get_match_status(match.date)
    ticket_prices = match.ticket_prices.all().order_by('price')
    match.status_key = status

    reviews = []
    user_review = None
    can_review = False
    avg_rating = 0

    if status == "Finished":
        reviews = Review.objects.filter(match=match).select_related("user").order_by("-created_at")
        avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"] or 0
        if request.user.is_authenticated:
            has_ticket = Ticket.objects.filter(
                ticket_type__match=match,
                booking__user=request.user,
                booking__status="CONFIRMED"
            ).exists()

            if has_ticket:
                can_review = True
                user_review = Review.objects.filter(user=request.user, match=match).first()

    context = {
        'match': match,
        'ticket_prices': ticket_prices,
        'messages_json': _get_cleaned_messages(request),
        'reviews': reviews,
        "avg_rating": round(avg_rating, 1),
        'user_review': user_review,
        'can_review': can_review,
    }

    return render(request, 'matches/details.html', context)


@user_passes_test(is_admin)
def update_matches_view(request):
    print("Memicu pembaruan database dari API...")
    message, sync_status = sync_database_with_apis()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':

        json_status = "error" if sync_status in ["error", "error_no_source"] else "success"

        return JsonResponse({
            'status': json_status,
            'message': message,
            'sync_source': sync_status
        })

    if sync_status not in ["error", "error_no_source"]:
        messages.success(request, message)
    else:
        messages.error(request, message)

    return redirect('matches:calendar')

def live_score_api(request, match_api_id):
    cache_key = f"live_score_single_{match_api_id}"
    cached_data = cache.get(cache_key)

    if cached_data:
        print(f"Mengambil live score untuk match {match_api_id} dari CACHE.")
        return JsonResponse(cached_data)

    print(f"Mengambil live score untuk match {match_api_id} dari Free API (Single Match).")

    url = "https://free-api-live-football-data.p.rapidapi.com/football-get-match"
    headers = {
        'x-rapidapi-key': settings.RAPID_API_KEY,
        'x-rapidapi-host': 'free-api-live-football-data.p.rapidapi.com'
    }
    params = {'matchid': match_api_id}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        api_data = response.json().get('response', {}).get('match', None)

        if not api_data:
            return JsonResponse({'error': 'Match not found in API'}, status=404)

        live_data = {
            'home_goals': api_data['home']['score'],
            'away_goals': api_data['away']['score'],
            'status_short': api_data['status']['short'],
            'status_long': api_data['status']['long'],
            'elapsed': api_data['status']['liveTime'].get('long', '0:00') if api_data['status'].get('liveTime') else '0:00',
        }

        cache.set(cache_key, live_data, timeout=10)
        return JsonResponse(live_data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class ManageBaseView(AdminRequiredMixin, ListView):
    model = Match
    template_name = 'matches/manage/match_list.html'
    context_object_name = 'matches'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'matches'
        context['action_url'] = reverse('matches:add_match')
        return context


class VenueListView(AdminRequiredMixin, ListView):
    model = Venue
    template_name = 'matches/manage/venue_list.html'
    context_object_name = 'venues'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'venues'
        context['action_url'] = reverse('matches:add_venue')
        return context

class VenueCreateView(AdminRequiredMixin, CreateView):
    model = Venue
    fields = ['name', 'city']
    template_name = 'matches/manage/venue_form.html'
    success_url = reverse_lazy('matches:manage_venues')

    def form_valid(self, form):
        messages.success(self.request, f'Venue "{form.instance.name}" berhasil ditambahkan.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = False
        context['current_page'] = 'venues'
        return context

class VenueUpdateView(AdminRequiredMixin, UpdateView):
    model = Venue
    fields = ['name', 'city']
    template_name = 'matches/manage/venue_form.html'
    success_url = reverse_lazy('matches:manage_venues')

    def form_valid(self, form):
        messages.success(self.request, f'Venue "{form.instance.name}" berhasil diperbarui.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = True
        context['current_page'] = 'venues'
        return context

class VenueDeleteView(AdminRequiredMixin, DeleteView):
    model = Venue
    template_name = 'matches/manage/venue_confirm_delete.html'
    success_url = reverse_lazy('matches:manage_venues')

    def form_valid(self, form):
        messages.success(self.request, f'Venue "{self.object.name}" berhasil dihapus.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_page'] = 'venues'
        return context


class TeamListView(AdminRequiredMixin, ListView):
    model = Team
    template_name = 'matches/manage/team_list.html'
    context_object_name = 'teams'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'teams'
        return context

class TeamCreateView(AdminRequiredMixin, CreateView):
    model = Team
    form_class = TeamForm
    template_name = 'matches/manage/team_form.html'
    success_url = reverse_lazy('matches:manage_teams')

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Tim "{self.object.name}" berhasil ditambahkan.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_update'] = False
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'teams'
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
        context['is_update'] = True
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'teams'
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
        context['current_page'] = 'teams'
        return context


class MatchListView(AdminRequiredMixin, ListView):
    model = Match
    template_name = 'matches/manage/match_list.html'
    context_object_name = 'matches'
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().select_related('home_team', 'away_team', 'venue').order_by('-date')

        request = self.request
        search_query = request.GET.get('q', '')
        date_start_filter = request.GET.get('date_start', '')
        date_end_filter = request.GET.get('date_end', '')
        venue_filter = request.GET.get('venue', '')
        status_filter_raw = request.GET.get('status', '')

        if search_query:
            queryset = queryset.filter(
                Q(home_team__name__icontains=search_query) |
                Q(away_team__name__icontains=search_query)
            )

        if venue_filter:
            queryset = queryset.filter(venue__id=venue_filter)

        if date_start_filter:
            try:
                start_date = dt.strptime(date_start_filter, '%Y-%m-%d').date()
                start_datetime = timezone.make_aware(dt.combine(start_date, time.min))

                if date_end_filter:
                    end_date = dt.strptime(date_end_filter, '%Y-%m-%d').date()
                    end_datetime = timezone.make_aware(dt.combine(end_date, time.max))
                    queryset = queryset.filter(date__range=(start_datetime, end_datetime))
                else:
                    end_datetime = timezone.make_aware(dt.combine(start_date, time.max))
                    queryset = queryset.filter(date__range=(start_datetime, end_datetime))
            except ValueError:
                pass

        if status_filter_raw:
            allowed_statuses = [s.strip() for s in status_filter_raw.split(',') if s.strip()]
            q_filter_status = Q()
            now = timezone.now()

            if 'Upcoming' in allowed_statuses:
                q_filter_status |= Q(date__gt=now)
            if 'Ongoing' in allowed_statuses:
                q_filter_status |= Q(date__lte=now, date__gt=now - timedelta(hours=2.5))
            if 'Finished' in allowed_statuses:
                q_filter_status |= Q(date__lte=now - timedelta(hours=2.5))
            
            if q_filter_status != Q():
                queryset = queryset.filter(q_filter_status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        
        context['messages_json'] = _get_cleaned_messages(request)
        context['current_page'] = 'matches'
        
        context['venues'] = Venue.objects.all().order_by('name')
        
        context['search_query'] = request.GET.get('q', '')
        context['selected_venue'] = request.GET.get('venue', '')
        context['date_start'] = request.GET.get('date_start', '')
        context['date_end'] = request.GET.get('date_end', '')
        context['selected_statuses'] = [s.strip() for s in request.GET.get('status', '').split(',') if s.strip()]

        if request.GET.get('date_end', ''):
             context['date_mode'] = 'range'
        else:
             context['date_mode'] = 'single'
             
        if not context['selected_statuses'] and 'status' not in request.GET:
            context['selected_statuses'] = ['Upcoming', 'Ongoing', 'Finished']

        return context

class MatchCreateUpdateMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        is_update_mode = self.object is not None and self.object.pk is not None

        if self.request.POST:
            context['formset'] = TicketPriceFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context['formset'] = TicketPriceFormSet(instance=self.object)

        context['is_update'] = is_update_mode
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'matches'
        return context

class MatchCreateView(AdminRequiredMixin, MatchCreateUpdateMixin, CreateView):
    model = Match
    form_class = MatchForm
    template_name = 'matches/manage/match_form.html'
    success_url = reverse_lazy('matches:manage_matches')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_match_live_or_finished'] = False
        context['current_page'] = 'matches'
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)

        if not self.object.pk:
            self.object.api_id = None
            self.object.status_short = "NS"
            self.object.status_long = "Not Started"
            self.object.home_goals = None
            self.object.away_goals = None

        self.object.save()
        form.save_m2m()

        formset = TicketPriceFormSet(self.request.POST, self.request.FILES, instance=self.object)

        if formset.is_valid():
            formset.save()

            messages.success(self.request, f'Pertandingan {self.object.home_team.name} vs {self.object.away_team.name} berhasil ditambahkan.')
            return redirect(self.get_success_url())
        else:
            messages.error(self.request, "Gagal menambahkan harga tiket. Pertandingan yang dibuat telah dihapus. Silakan coba lagi.")
            self.object.delete()

            context = self.get_context_data(form=form)
            context['formset'] = formset
            return self.render_to_response(context)

class MatchUpdateView(AdminRequiredMixin, MatchCreateUpdateMixin, UpdateView):
    model = Match
    form_class = MatchForm
    template_name = 'matches/manage/match_form.html'
    success_url = reverse_lazy('matches:manage_matches')

    def get_queryset(self):
        return super().get_queryset().select_related('home_team', 'away_team')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        status = get_match_status(self.object.date)
        context['is_match_live_or_finished'] = status in ['Ongoing', 'Finished']

        context['is_update'] = True
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'matches'
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)

        self.object.save()
        form.save_m2m()

        formset = TicketPriceFormSet(self.request.POST, self.request.FILES, instance=self.object)

        if formset.is_valid():
            formset.save()

            messages.success(self.request, f'Pertandingan {self.object.home_team.name} vs {self.object.away_team.name} berhasil diperbarui.')
            return redirect(self.get_success_url())
        else:
            messages.error(self.request, "Gagal memperbarui harga tiket.")

            context = self.get_context_data(form=form)
            context['formset'] = formset
            return self.render_to_response(context)

class MatchDeleteView(AdminRequiredMixin, DeleteView):
    model = Match
    template_name = 'matches/manage/match_confirm_delete.html'
    success_url = reverse_lazy('matches:manage_matches')

    def form_valid(self, form):
        match_info = f"{self.object.home_team.name} vs {self.object.away_team.name}"
        messages.success(self.request, f'Pertandingan {match_info} berhasil dihapus.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['messages_json'] = _get_cleaned_messages(self.request)
        context['current_page'] = 'matches'
        return context
