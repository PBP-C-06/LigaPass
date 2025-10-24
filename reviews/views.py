from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string

from matches.models import Match
from reviews.models import Review, ReviewReply
from bookings.models import Ticket
import json

def is_admin(user):
    return user.is_authenticated and getattr(user, "role", None) == "admin"

def is_user(user):
    return user.is_authenticated and getattr(user, "role", None) == "user"


@user_passes_test(is_user)
@login_required
def user_review_page(request, match_id):
    """
    Komponen review untuk sebuah match.
    Ditampilkan di halaman detail tiket (dari app bookings).
    """
    match = get_object_or_404(
        Match.objects.select_related("home_team", "away_team"),
        id=match_id
    )

    # Pastikan user punya tiket yang dikonfirmasi
    has_ticket = Ticket.objects.filter(
        ticket_type__match=match,
        booking__user=request.user,
        booking__status="CONFIRMED"
    ).exists()
    if not has_ticket:
        return render(
            request,
            "reviews/no_access.html",
            {"message": "Kamu belum membeli tiket untuk pertandingan ini."},
        )

    my_review = Review.objects.filter(user=request.user, match=match).first()
    reviews = Review.objects.filter(match=match).select_related("user").order_by("-created_at")

    return render(
        request,
        "reviews/user_review_page.html",
        {
            "match": match,
            "my_review": my_review,
            "reviews": reviews,
        },
    )


@csrf_exempt
@user_passes_test(is_user)
@login_required
def api_create_review(request, match_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    match = get_object_or_404(Match, id=match_id)

    has_booking = Ticket.objects.filter(
        ticket_type__match=match,
        booking__user=request.user,
        booking__status="CONFIRMED",
    ).exists()
    if not has_booking:
        return JsonResponse({"ok": False, "message": "Kamu hanya bisa mereview pertandingan yang sudah kamu beli tiketnya."}, status=403)

    if Review.objects.filter(match=match, user=request.user).exists():
        return JsonResponse({"ok": False, "message": "Kamu sudah pernah mereview pertandingan ini. Gunakan Edit."}, status=400)

    rating = int(request.POST.get("rating", 0))
    comment = (request.POST.get("comment") or "").strip()
    if not (1 <= rating <= 5):
        return JsonResponse({"ok": False, "message": "Rating harus 1–5."}, status=400)

    review = Review.objects.create(user=request.user, match=match, rating=rating, comment=comment)
    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)

    return JsonResponse({"ok": True, "message": "Review berhasil ditambahkan", "item_html": html_item, "review_id": str(review.id)})


@csrf_exempt
@user_passes_test(is_user)
@login_required
def api_update_review(request, match_id):
    if request.method not in ("POST", "PUT", "PATCH"):
        return HttpResponseBadRequest("POST/PUT only")

    match = get_object_or_404(Match, id=match_id)
    review = get_object_or_404(Review, match=match, user=request.user)

    data = {}
    if request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "message": "Invalid JSON format."}, status=400)

    rating = int(data.get("rating", request.POST.get("rating", review.rating)))
    comment = (data.get("comment", request.POST.get("comment", review.comment)) or "").strip()

    if not (1 <= rating <= 5):
        return JsonResponse({"ok": False, "message": "Rating harus 1–5."}, status=400)

    review.rating = rating
    review.comment = comment
    review.save(update_fields=["rating", "comment", "updated_at"])

    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)
    return JsonResponse({"ok": True, "message": "Review berhasil diperbarui", "item_html": html_item, "review_id": str(review.id)})

# === ADMIN REVIEWS ===
@user_passes_test(is_admin)
@login_required
def admin_review_page(request, match_id):
    """
    Ditampilkan di halaman detail tiket admin.
    Menampilkan semua review user untuk 1 pertandingan.
    """
    match = get_object_or_404(Match.objects.select_related("home_team", "away_team"), id=match_id)
    reviews = Review.objects.filter(match=match).select_related("user", "reply").order_by("-created_at")

    return render(request, "reviews/admin_review_page.html", {
        "match": match,
        "reviews": reviews,
    })


@csrf_exempt
@user_passes_test(is_admin)
@login_required
def api_add_reply(request, review_id):
    """
    Admin menambahkan balasan ke review (via modal pop-up di admin_review_page).
    Review hanya bisa dibalas satu kali (OneToOne).
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=400)

    review = get_object_or_404(Review, id=review_id)

    # Validasi: jika sudah dibalas, tolak
    if hasattr(review, "reply"):
        return JsonResponse({"status": "error", "message": "Review ini sudah memiliki balasan."}, status=400)

    # Ambil teks balasan
    reply_text = (request.POST.get("reply_text") or "").strip()
    if not reply_text:
        return JsonResponse({"status": "error", "message": "Balasan tidak boleh kosong."}, status=400)

    # Simpan balasan
    reply = ReviewReply.objects.create(
        review=review,
        admin=request.user,
        reply_text=reply_text
    )

    # Render ulang elemen review agar langsung diperbarui di front-end
    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)

    return JsonResponse({
        "status": "success",
        "message": "Balasan berhasil disimpan.",
        "reply_text": reply.reply_text,
        "review_id": str(review.id),
        "updated_html": html_item,
    })

# fungsi di bawah ini supaya balasan dari admin bisa diedit atau dihapus via ajax
@csrf_exempt
@user_passes_test(is_admin)
@login_required
def api_edit_reply(request, review_id):
    """
    Admin mengedit balasan ke review (via modal pop-up di admin_review_page).
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=400)

    review = get_object_or_404(Review, id=review_id)

    # Validasi: jika belum dibalas, tolak
    if not hasattr(review, "reply"):
        return JsonResponse({"status": "error", "message": "Review ini belum memiliki balasan."}, status=400)

    # Ambil teks balasan
    reply_text = (request.POST.get("reply_text") or "").strip()
    if not reply_text:
        return JsonResponse({"status": "error", "message": "Balasan tidak boleh kosong."}, status=400)

    # Simpan balasan
    review.reply.reply_text = reply_text
    review.reply.save(update_fields=["reply_text", "created_at"])

    # Render ulang elemen review agar langsung diperbarui di front-end
    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)

    return JsonResponse({
        "status": "success",
        "message": "Balasan berhasil diperbarui.",
        "reply_text": review.reply.reply_text,
        "review_id": str(review.id),
        "updated_html": html_item,
    })

@csrf_exempt
@user_passes_test(is_admin)
@login_required
def api_delete_reply(request, review_id):
    """
    Admin menghapus balasan ke review (via modal pop-up di admin_review_page).
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=400)

    review = get_object_or_404(Review, id=review_id)

    # Validasi: jika belum dibalas, tolak
    if not hasattr(review, "reply"):
        return JsonResponse({"status": "error", "message": "Review ini belum memiliki balasan."}, status=400)

    # Hapus balasan
    review.reply.delete()

    # Render ulang elemen review agar langsung diperbarui di front-end
    html_item = render_to_string("reviews/_review_item.html", {"review": review}, request=request)

    return JsonResponse({
        "status": "success",
        "message": "Balasan berhasil dihapus.",
        "review_id": str(review.id),
        "updated_html": html_item,
    })
