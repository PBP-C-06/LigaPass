from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from matches.models import Match
from news.models import News

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

    return render(request, "main_page.html", {
        "hero_slides": hero_slides,
        "upcoming_matches": upcoming_matches,
        "latest_news": latest_news,
    })
