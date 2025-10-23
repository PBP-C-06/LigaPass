from django.shortcuts import render
from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from matches.models import Match
from news.models import News

def current_user_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})

    user = request.user
    profile = getattr(user, "profile", None)

    # Tentukan url profile picture berdasarkan role
    if user.role == "admin":
        profile_picture_url = static("images/Admin.png")
        my_profile_url = reverse("profiles:admin_view")
    elif user.role == "journalist":
        profile_picture_url = static("images/Journalist.png")
        my_profile_url = reverse("profiles:journalist_view")
    else:
        if profile and profile.profile_picture:
            profile_picture_url = profile.profile_picture.url
        else:
            profile_picture_url = static("images/default-profile-picture.png")
        my_profile_url = reverse("profiles:user_view", args=[user.id])

    my_bookings_url = reverse("profiles:user_view", args=[user.id]) # GUYS JGN LUPA DIGANTI!!!!
    my_analytics_url = reverse("profiles:user_view", args=[user.id]) # GUYS JGN LUPA DIGANTI!!!!

    return JsonResponse({
        "authenticated": True,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "id": str(user.id),
        "profile_picture": profile_picture_url,
        "my_profile_url": my_profile_url,
        "my_bookings_url": my_bookings_url,
        "my_analytics_url": my_analytics_url,
    })


def home(request):
    now = timezone.now()
    upcoming_threshold = now

    # === Ambil 5 pertandingan mendatang ===
    upcoming_matches = (
        Match.objects.select_related("home_team", "away_team", "venue")
        .filter(date__gt=upcoming_threshold)
        .order_by("date")[:5]
    )

    # === Ambil 3 berita terbaru ===
    featured_news = list(News.objects.filter(is_featured=True).order_by("-created_at")[:3])
    if len(featured_news) < 3:
        additional_news = list(
            News.objects.filter(is_featured=False)
            .exclude(id__in=[n.id for n in featured_news])
            .order_by("-created_at")[: 3 - len(featured_news)]
        )
        latest_news = featured_news + additional_news
    else:
        latest_news = featured_news

    # === Hero slides ===
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

    context = {
        "hero_slides": hero_slides,
        "upcoming_matches": upcoming_matches,
        "latest_news": latest_news,
    }

    return render(request, "main_page.html", context)