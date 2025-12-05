from django.shortcuts import render
from django.utils import timezone
from django.templatetags.static import static
from matches.models import Match, Team
from news.models import News
from django.http import JsonResponse
from django.views.decorators.http import require_GET

def home(request):
    now = timezone.now()

    # === Ambil 5 pertandingan mendatang ===
    upcoming_matches = (
        Match.objects.select_related("home_team", "away_team", "venue")
        .filter(date__gt=now)
        .order_by("date")[:5]
    )

    # === Ambil 6 berita terbaru (prioritaskan featured) ===
    featured = list(News.objects.filter(is_featured=True).order_by("-created_at")[:3])
    additional = list(
        News.objects.filter(is_featured=False)
        .exclude(id__in=[n.id for n in featured])
        .order_by("-created_at")[: max(0, 6 - len(featured))]
    )
    latest_news = featured + additional

    # === Hero Slides ===
    hero_slides = [
        {
            "title": "Rasakan Setiap Pertandingan Secara Langsung",
            "description": "Lihat jadwal, tim, dan amankan tiket Anda sekarang!",
            "image": static("images/banner1.jpeg"),
            "cta_text": "Beli Tiket",
            "cta_link": "/matches/",
        },
        {
            "title": "Akses Eksklusif Liga Utama",
            "description": "Dapatkan tiket untuk pertandingan paling ditunggu!",
            "image": static("images/banner2.jpeg"),
            "cta_text": "Lihat Tiket",
            "cta_link": "/matches/",
        },
        {
            "title": "Berita Sepak Bola Terkini",
            "description": "Ikuti kabar terbaru dan analisis mendalam tentang sepak bola.",
            "image": static("images/banner3.jpeg"),
            "cta_text": "Baca Berita",
            "cta_link": "/news/",
        },
    ]

    all_teams = Team.objects.all()

    return render(request, "main_page.html", {
        "hero_slides": hero_slides,
        "upcoming_matches": upcoming_matches,
        "latest_news": latest_news,
        "teams": all_teams,
    })

@require_GET
def api_flutter_home(request):
    """
    REST API endpoint untuk Flutter homepage.
    Returns upcoming matches, latest news, dan all teams.
    """
    from django.urls import reverse
    
    now = timezone.now()

    # === 5 pertandingan mendatang ===
    upcoming_matches = (
        Match.objects.select_related("home_team", "away_team", "venue")
        .filter(date__gt=now)
        .order_by("date")[:5]
    )

    matches_data = []
    for match in upcoming_matches:
        # Use proxy URL like in matches/views.py
        home_logo = ""
        away_logo = ""
        if match.home_team:
            home_logo = request.build_absolute_uri(
                reverse('matches:flutter_team_logo_proxy', args=[match.home_team.id])
            )
        if match.away_team:
            away_logo = request.build_absolute_uri(
                reverse('matches:flutter_team_logo_proxy', args=[match.away_team.id])
            )
        
        matches_data.append({
            "id": str(match.id),
            "home_team_name": match.home_team.name if match.home_team else "",
            "away_team_name": match.away_team.name if match.away_team else "",
            "home_team_logo": home_logo,
            "away_team_logo": away_logo,
            "venue": match.venue.name if match.venue else "",
            "match_date": match.date.isoformat() if match.date else "",
            "status": "upcoming",
        })

    # === 6 berita terbaru (prioritaskan featured) ===
    featured = list(News.objects.filter(is_featured=True).order_by("-created_at")[:3])
    additional = list(
        News.objects.filter(is_featured=False)
        .exclude(id__in=[n.id for n in featured])
        .order_by("-created_at")[: max(0, 6 - len(featured))]
    )
    latest_news = featured + additional

    news_data = []
    for news in latest_news:
        news_data.append({
            "id": news.id,
            "title": news.title,
            "content": news.content[:200] + "..." if len(news.content) > 200 else news.content,
            "thumbnail": request.build_absolute_uri(news.thumbnail.url) if news.thumbnail else "",
            "category": news.category,
            "is_featured": news.is_featured,
            "created_at": news.created_at.strftime("%Y-%m-%d %H:%M") if news.created_at else "",
        })

    # === Semua team - use proxy URL ===
    all_teams = Team.objects.all()
    teams_data = []
    for team in all_teams:
        logo_url = request.build_absolute_uri(
            reverse('matches:flutter_team_logo_proxy', args=[team.id])
        )
        teams_data.append({
            "id": str(team.id),
            "name": team.name,
            "logo_url": logo_url,
        })

    return JsonResponse({
        "upcoming_matches": matches_data,
        "latest_news": news_data,
        "teams": teams_data,
    })