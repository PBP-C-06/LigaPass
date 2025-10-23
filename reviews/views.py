from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.db.models import Q
from django.urls import reverse

from matches.models import Match, Team
from reviews.models import Review, ReviewReply
from bookings.models import Ticket
from django.conf import settings

import json

def is_admin(user):
    """Cek apakah user merupakan admin (berdasarkan role atau bawaan Django)."""
    return user.is_authenticated and getattr(user, "role", None) == "admin"


def is_user(user):
    """Cek apakah user merupakan user biasa (bukan admin atau jurnalis)."""
    return user.is_authenticated and getattr(user, "role", None) == "user"

@user_passes_test(is_user)
@login_required
def user_review_entry(request):
    """
    - Hanya menampilkan match yang SUDAH dibeli user (Booking.status='CONFIRMED')
    - Jika ada ?team=... → filter match terakhir untuk tim itu.
    - Jika tidak → pilih match terakhir yang pernah user beli.
    - Jika belum ada match yang dibeli → tampilkan halaman 'user_no_match'.
    - Jika sudah review → redirect ke /user/<match_id>/
    - Jika belum review → redirect ke /user/<match_id>/?autopop=1
    """

    team_name = (request.GET.get("team") or "").strip()
    qs = Match.objects.filter(
        ticket_prices__ticket__booking__user=request.user,
        ticket_prices__ticket__booking__status="CONFIRMED",
    ).select_related("home_team", "away_team").distinct().order_by("-date")

    if team_name:
        qs = qs.filter(
            Q(home_team__name=team_name) | Q(away_team__name=team_name)
        )

    match = qs.first()
    if not match:
        return render(request, "reviews/user_no_match.html", {
            "message": "Kamu belum membeli tiket untuk pertandingan ini.",
            "teams": Team.objects.all().order_by("name"),
            "selected_team": team_name,
        })

    has_review = Review.objects.filter(match=match, user=request.user).exists()

    url = reverse("reviews:user_review_page", args=[str(match.id)])
    if not has_review:
        return redirect(f"{url}?autopop=1&team={team_name}")
    else:
        return redirect(f"{url}?team={team_name}")


@user_passes_test(is_user)
@login_required
def user_review_page(request, match_id):
    """Tampilkan halaman review user untuk satu match tertentu."""
    match = get_object_or_404(
        Match.objects.select_related("home_team", "away_team"), id=match_id
    )
    teams = Team.objects.all().order_by("name")
    selected_team = (request.GET.get("team") or "").strip()

    reviews = (
        Review.objects
        .filter(match=match)
        .select_related("user", "reply")
        .order_by("-created_at")
    )

    my_review = reviews.filter(user=request.user).first()
    autopop = request.GET.get("autopop") == "1" and (my_review is None)

    # ⚙️ FIXED: convert my_review ke dict agar tidak error JSON
    my_review_dict = None
    if my_review:
        my_review_dict = {
            "id": str(my_review.id),
            "rating": my_review.rating,
            "comment": my_review.comment,
            "user": my_review.user.username,
        }

    return render(request, "reviews/user_review_page.html", {
        "match": match,
        "reviews": reviews,
        "my_review": my_review_dict,
        "teams": teams,
        "selected_team": selected_team,
        "autopop": autopop,
    })



@csrf_exempt
@user_passes_test(is_user)
@login_required
def api_create_review(request, match_id):
    """API untuk membuat review baru oleh user biasa."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    match = get_object_or_404(Match, id=match_id)

    # Pastikan user beli tiket
    has_booking = Ticket.objects.filter(
        ticket_type__match=match,
        booking__user=request.user,
        booking__status="CONFIRMED",
    ).exists()
    if not has_booking:
        return JsonResponse({
            "ok": False,
            "message": "Kamu hanya bisa mereview pertandingan yang sudah kamu beli tiketnya."
        }, status=403)

    # Cegah duplikat
    if Review.objects.filter(match=match, user=request.user).exists():
        return JsonResponse({
            "ok": False,
            "message": "Kamu sudah pernah mereview pertandingan ini. Gunakan Edit."
        }, status=400)

    # Validasi input
    rating = int(request.POST.get("rating", 0))
    comment = (request.POST.get("comment") or "").strip()
    if not (1 <= rating <= 5):
        return JsonResponse({"ok": False, "message": "Rating harus 1–5."}, status=400)

    # Buat review
    review = Review.objects.create(
        user=request.user,
        match=match,
        rating=rating,
        comment=comment,
    )

    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)
    return JsonResponse({
        "ok": True,
        "message": "Review berhasil ditambahkan",
        "item_html": html_item,
        "review_id": str(review.id)
    })


@csrf_exempt
@user_passes_test(is_user)
@login_required
def api_update_review(request, match_id):
    """API untuk memperbarui review user."""
    if request.method not in ("POST", "PUT", "PATCH"):
        return HttpResponseBadRequest("POST/PUT only")

    match = get_object_or_404(Match, id=match_id)
    review = get_object_or_404(Review, match=match, user=request.user)

    if request.content_type == "application/json":
        data = json.loads(request.body.decode("utf-8"))
        rating = int(data.get("rating", review.rating))
        comment = (data.get("comment") or review.comment or "").strip()
    else:
        rating = int(request.POST.get("rating", review.rating))
        comment = (request.POST.get("comment") or review.comment or "").strip()

    if not (1 <= rating <= 5):
        return JsonResponse({"ok": False, "message": "Rating harus 1–5."}, status=400)

    review.rating = rating
    review.comment = comment
    review.save(update_fields=["rating", "comment", "updated_at"])

    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)
    return JsonResponse({
        "ok": True,
        "message": "Review berhasil diperbarui",
        "item_html": html_item,
        "review_id": str(review.id)
    })


@user_passes_test(is_admin)
@login_required
def admin_review_page(request):
    """Halaman admin untuk melihat dan membalas review user."""
    selected_match_id = request.GET.get("match")
    sentiment = request.GET.get("sentiment")

    if selected_match_id:
        match = get_object_or_404(Match, id=selected_match_id)
        reviews = Review.objects.filter(match=match).select_related("user", "reply")
    else:
        match = None
        reviews = Review.objects.select_related("user", "reply")

    # Filter kategori sentimen
    if sentiment == "baik":
        reviews = reviews.filter(rating__gte=4)
    elif sentiment == "netral":
        reviews = reviews.filter(rating=3)
    elif sentiment == "buruk":
        reviews = reviews.filter(rating__lte=2)

    context = {
        "matches": Match.objects.all(),
        "selected_match": match,
        "reviews": reviews,
        "sentiment": sentiment,
    }
    return render(request, "reviews/admin_review_page.html", context)


@csrf_exempt
@user_passes_test(is_admin)
@login_required
def api_add_reply(request, review_id):
    """API untuk admin menambahkan atau mengedit balasan review."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=400)

    review = get_object_or_404(Review, id=review_id)
    data = json.loads(request.body.decode("utf-8"))
    reply_text = data.get("reply_text")

    if not reply_text.strip():
        return JsonResponse({"status": "error", "message": "Balasan tidak boleh kosong."}, status=400)

    reply, created = ReviewReply.objects.get_or_create(
        review=review,
        defaults={"admin": request.user, "reply_text": reply_text}
    )

    if not created:
        reply.reply_text = reply_text
        reply.save()

    return JsonResponse({
        "status": "success",
        "message": "Balasan berhasil disimpan.",
        "reply_text": reply.reply_text,
        "review_id": str(review.id)
    })
