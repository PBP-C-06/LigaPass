from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db.models.functions import (
    TruncDay, TruncWeek, TruncMonth,
    ExtractDay, ExtractWeek, ExtractMonth, ExtractYear
)
from bookings.models import Booking, Ticket
from matches.models import Match
from reviews.models import Review
from django.utils.timezone import now


# === ROLE CHECKERS ===
def is_admin(user):
    return user.is_authenticated and getattr(user, "role", None) == "admin"


def is_user(user):
    return user.is_authenticated and getattr(user, "role", None) == "user"


# ==============================
#         ADMIN ANALYTICS
# ==============================

@login_required
@user_passes_test(is_admin)
def admin_analytics_page(request):
    """Halaman Analytics untuk Admin"""
    return render(request, "reviews/admin_analytics.html")


@login_required
@user_passes_test(is_admin)
def api_admin_analytics_data(request):
    """API Admin Analytics"""
    period = request.GET.get("period", "monthly").lower()

    if period == "daily":
        trunc = TruncDay("created_at")
    elif period == "weekly":
        trunc = TruncWeek("created_at")
    else:
        trunc = TruncMonth("created_at")

    confirmed_bookings = Booking.objects.filter(status="CONFIRMED")

    revenue_data = (
        confirmed_bookings
        .annotate(period=trunc)
        .values("period")
        .annotate(total_revenue=Sum("total_price"))
        .order_by("period")
    )

    tickets_data = (
        Ticket.objects.filter(booking__status="CONFIRMED")
        .annotate(period=trunc)
        .values("period")
        .annotate(tickets_sold=Count("ticket_id"))
        .order_by("period")
    )

    revenue_list = [
        {
            "date": r["period"].strftime("%d/%m/%Y") if r["period"] else None,
            "total_revenue": float(r["total_revenue"] or 0),
        }
        for r in revenue_data
    ]

    tickets_list = [
        {
            "date": t["period"].strftime("%d/%m/%Y") if t["period"] else None,
            "tickets_sold": t["tickets_sold"],
        }
        for t in tickets_data
    ]

    return JsonResponse({
        "revenueData": revenue_list,
        "ticketsData": tickets_list,
    })


# ==============================
#          USER ANALYTICS
# ==============================

@login_required
@user_passes_test(is_user)
def user_analytics_page(request):
    """Halaman Analytics untuk User"""
    return render(request, "reviews/user_analytics.html")


@login_required
@user_passes_test(is_user)
def api_user_analytics_data(request):
    """API User Analytics"""
    period = request.GET.get("period", "daily").lower()
    today = now().date()

    bookings = Booking.objects.filter(
        user=request.user,
        status="CONFIRMED",
        created_at__isnull=False
    )

    # === Filter Berdasarkan Periode ===
    if period == "daily":
        # hanya hari ini
        bookings = bookings.filter(created_at__date=today)
        trunc_field = TruncDay("created_at")

    elif period == "weekly":
        # minggu ini (Senin–Minggu)
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        bookings = bookings.filter(created_at__date__range=[start_week, end_week])
        trunc_field = TruncDay("created_at")

    else:  # monthly
        # bulan ini, dikelompokkan per minggu (Minggu 1–4)
        start_month = today.replace(day=1)
        end_month = (start_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        bookings = bookings.filter(created_at__date__range=[start_month, end_month])
        trunc_field = ExtractWeek("created_at")

    # === Total Pengeluaran ===
    spending_data = (
        bookings
        .annotate(period=trunc_field)
        .values("period")
        .annotate(total_spent=Sum("total_price"))
        .order_by("period")
    )

    # === Format Data untuk Chart ===
    spending_list = []

    if period == "daily":
        total = spending_data[0]["total_spent"] if spending_data else 0
        spending_list.append({
            "date": today.strftime("%d/%m/%Y"),
            "total_spent": float(total)
        })

    elif period == "weekly":
        # Buat label Senin–Minggu
        day_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        day_map = {i + 1: name for i, name in enumerate(day_names)}  # 1–7
        day_totals = {item["period"].day: float(item["total_spent"]) for item in spending_data}

        for i in range(1, 8):
            spending_list.append({
                "date": day_map.get(i, f"Hari {i}"),
                "total_spent": day_totals.get(i, 0.0)
            })

    else:  # monthly
        # 4 minggu dalam sebulan (minggu ke-1 sampai ke-4)
        week_totals = list(spending_data)
        for idx in range(1, 5):
            value = 0.0
            if idx - 1 < len(week_totals):
                value = float(week_totals[idx - 1]["total_spent"] or 0)
            spending_list.append({
                "date": f"Minggu {idx}",
                "total_spent": value
            })

    # === Seat Count ===
    tickets = Ticket.objects.filter(booking__in=bookings).select_related("ticket_type")
    seat_count = (
        tickets.values("ticket_type__seat_category")
        .annotate(count=Count("ticket_id"))
        .order_by("ticket_type__seat_category")
    )

    # === Kehadiran ===
    total_matches = Match.objects.filter(
        ticket_prices__ticket__booking__user=request.user
    ).distinct().count()

    reviewed_matches = Review.objects.filter(user=request.user).count()
    attendance = {
        "hadir": reviewed_matches,
        "tidak_hadir": max(total_matches - reviewed_matches, 0)
    }

    return JsonResponse({
        "spendingData": spending_list,
        "seatCount": list(seat_count),
        "attendance": attendance,
    })
