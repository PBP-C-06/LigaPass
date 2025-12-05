from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.db.models import Avg
from matches.models import Match
from reviews.models import Review, ReviewReply
from bookings.models import Ticket
import json

@csrf_exempt
@login_required
def user_review_page(request, match_id):
    if getattr(request.user, "role", None) != "user":
        return redirect("main:home")
    match = get_object_or_404(
        Match.objects.select_related("home_team", "away_team"),
        id=match_id
    )

    # Cek apakah user punya tiket valid
    has_ticket = Ticket.objects.filter(
        ticket_type__match=match,
        booking__user=request.user,
        booking__status="CONFIRMED"
    ).exists()

    if not has_ticket:
        messages.error(request, "Kamu belum membeli tiket untuk pertandingan ini.")
        return redirect("main:home")

    my_review = Review.objects.filter(user=request.user, match=match).first()
    reviews = Review.objects.filter(match=match).select_related("user").order_by("-created_at")

    return render(request, "user_review_page.html", {
        "match": match,
        "my_review": my_review,
        "reviews": reviews,
    })


@csrf_exempt
@login_required
def api_create_review(request, match_id):

    if getattr(request.user, "role", None) != "user":
        return JsonResponse({"ok": False, "message": "Hanya user yang bisa memberi review."}, status=403)
    
    status = getattr(request.user.profile, "status", "active")
    if status != "active":
        return JsonResponse({"ok": False, "message": f"Akun Anda sedang {status}. Tidak bisa review."}, status=403)
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")

    match = get_object_or_404(Match, id=match_id)
    has_booking = Ticket.objects.filter(
        ticket_type__match=match,
        booking__user=request.user,
        booking__status="CONFIRMED"
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
    html_item = render_to_string("_review_item.html", {"review": review}, request=request)

    return JsonResponse({"ok": True, "message": "Review berhasil ditambahkan", "item_html": html_item, "review_id": str(review.id)})


@csrf_exempt
@login_required
def api_update_review(request, match_id):
    if getattr(request.user, "role", None) != "user":
        return JsonResponse({"ok": False, "message": "Hanya user yang bisa memberi review."}, status=403)

    status = getattr(request.user.profile, "status", "active")
    if status != "active":
        return JsonResponse({"ok": False, "message": f"Akun Anda sedang {status}. Tidak bisa edit review."}, status=403)
  
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

    html_item = render_to_string("_review_item.html", {"review": review}, request=request)
    return JsonResponse({"ok": True, "message": "Review berhasil diperbarui", "item_html": html_item, "review_id": str(review.id)})


@csrf_exempt
@login_required
def admin_review_page(request, match_id):
    if getattr(request.user, "role", None) != "admin":
        return redirect("main:home")
    match = get_object_or_404(Match.objects.select_related("home_team", "away_team"), id=match_id)
    reviews = Review.objects.filter(match=match).select_related("user", "reply").order_by("-created_at")
    return render(request, "admin_review_page.html", {"match": match, "reviews": reviews})


@csrf_exempt
@login_required
def api_add_reply(request, review_id):
    if getattr(request.user, "role", None) != "admin":
        return JsonResponse({"ok": False, "message": "Halaman yang anda coba lihat hanya untuk admin"}, status=403)
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=400)

    review = get_object_or_404(Review, id=review_id)

    if hasattr(review, "reply"):
        return JsonResponse({"status": "error", "message": "Review ini sudah memiliki balasan."}, status=400)

    reply_text = (request.POST.get("reply_text") or "").strip()
    if not reply_text:
        return JsonResponse({"status": "error", "message": "Balasan tidak boleh kosong."}, status=400)

    reply = ReviewReply.objects.create(review=review, admin=request.user, reply_text=reply_text)
    html_item = render_to_string("_review_item.html", {"review": review}, request=request)

    return JsonResponse({"status": "success", "message": "Balasan berhasil disimpan.", "reply_text": reply.reply_text, "review_id": str(review.id), "updated_html": html_item, "reply_id": str(reply.id)})

@csrf_exempt
@login_required
def api_list_reviews(request, match_id):
    # Hanya role user yang boleh akses
    if getattr(request.user, "role", None) != "user":
        return JsonResponse({"ok": False, "message": "Hanya user yang bisa mengakses."}, status=403)

    match = get_object_or_404(Match, id=match_id)

    # Cek apakah user memiliki tiket valid
    from bookings.models import Ticket
    has_ticket = Ticket.objects.filter(
        ticket_type__match=match,
        booking__user=request.user,
        booking__status="CONFIRMED"
    ).exists()

    # Ambil review user (jika ada)
    my_review = Review.objects.filter(
        user=request.user,
        match=match
    ).first()

    my_review_json = None
    if my_review:
        my_review_json = {
        "id": my_review.id,
        "rating": my_review.rating,
        "comment": my_review.comment,
        "sentiment": my_review.sentiment,
        "created_at": my_review.created_at.isoformat(),
        "updated_at": my_review.updated_at.isoformat(),
        "reply": (
            {
                "id": my_review.reply.id,
                "admin": my_review.reply.admin.username if my_review.reply.admin else None,
                "reply_text": my_review.reply.reply_text,
                "created_at": my_review.reply.created_at.isoformat(),
            }
            if hasattr(my_review, "reply")
            else None
        )
    }

    # Ambil review orang lain
    other_reviews = (
        Review.objects.filter(match=match)
        .exclude(user=request.user)
        .select_related("user", "reply")
        .order_by("-created_at")
    )

    reviews_json = []
    for r in other_reviews:
        reviews_json.append({
            "id": r.id,
            "user": r.user.username,
            "rating": r.rating,
            "comment": r.comment,
            "sentiment": r.sentiment,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
            "reply": (
                {
                    "admin": r.reply.admin.username if r.reply.admin else None,
                    "reply_text": r.reply.reply_text,
                    "created_at": r.reply.created_at.isoformat(),
                }
                if hasattr(r, "reply")
                else None
            )
        })

    # Hitung rata-rata rating
    avg_rating = Review.objects.filter(match=match).aggregate(avg=Avg("rating"))["avg"]

    return JsonResponse({
        "ok": True,
        "my_review": my_review_json,
        "reviews": reviews_json,
        "average_rating": avg_rating,
        "has_ticket": has_ticket,
        "can_review": has_ticket and (my_review is None),
    })

@csrf_exempt
@login_required
def api_list_reviews_admin(request, match_id):
    if getattr(request.user, "role", None) != "admin":
        return JsonResponse({"ok": False, "message": "Admin only"}, status=403)

    match = get_object_or_404(Match, id=match_id)

    reviews_qs = Review.objects.filter(match=match).select_related("user", "reply")

    average_rating = reviews_qs.aggregate(avg=Avg("rating"))["avg"]
    if average_rating is None:
        average_rating = 0.0

    total_reviews = reviews_qs.count()

    reviews_json = []
    for r in reviews_qs.order_by("-created_at"):
        reviews_json.append({
            "id": r.id,
            "user": r.user.username,
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.isoformat(),
            "reply": (
                    {
                        "id": r.reply.id,
                        "reply_text": r.reply.reply_text,
                        "admin": r.reply.admin.username if r.reply.admin else None,
                        "created_at": r.reply.created_at.isoformat(),
                    }
                    if hasattr(r, "reply") else None
                )
        })

    return JsonResponse({
        "ok": True,
        "average_rating": round(float(average_rating), 1),
        "total_reviews": total_reviews,
        "reviews": reviews_json,
    })


@csrf_exempt
@login_required
def api_edit_reply(request, reply_id):
    if getattr(request.user, "role", None) != "admin":
        return JsonResponse({"status": "error", "message": "Admin only"}, status=403)

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST required"}, status=400)

    reply = get_object_or_404(ReviewReply, id=reply_id)

    new_text = (request.POST.get("reply_text") or "").strip()
    if not new_text:
        return JsonResponse({"status": "error", "message": "Reply cannot be empty"}, status=400)

    reply.reply_text = new_text
    reply.save(update_fields=["reply_text"])

    return JsonResponse({
        "status": "success",
        "message": "Reply updated",
        "reply": {
            "id": reply.id,
            "reply_text": reply.reply_text,
            "admin": reply.admin.username if reply.admin else None,
            "created_at": reply.created_at.isoformat()
        }
    })

@csrf_exempt
@login_required
def api_delete_reply(request, reply_id):
    if getattr(request.user, "role", None) != "admin":
        return JsonResponse({"status": "error", "message": "Admin only"}, status=403)

    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST required"}, status=400)

    reply = get_object_or_404(ReviewReply, id=reply_id)
    reply.delete()

    return JsonResponse({
        "status": "success",
        "message": "Reply deleted",
        "reply_id": reply_id
    })

