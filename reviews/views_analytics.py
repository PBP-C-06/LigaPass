from datetime import datetime, timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, ExtractWeek
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
    return render(request, "admin_analytics.html")


@login_required
@user_passes_test(is_admin)
def api_admin_analytics_data(request):
    """API untuk data Admin Analytics"""
    period = request.GET.get("period", "monthly").lower()
    today = now().date()

    # === Tentukan range & granularity waktu ===
    if period == "daily":
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())
        trunc_expr = TruncDay("created_at")

    elif period == "weekly":
        start_week = today - timedelta(days=today.weekday())  # Senin
        end_week = start_week + timedelta(days=6)             # Minggu
        start_dt = datetime.combine(start_week, datetime.min.time())
        end_dt = datetime.combine(end_week, datetime.max.time())
        trunc_expr = TruncDay("created_at")

    else:  # monthly
        start_month = today.replace(day=1)
        next_month = (start_month + timedelta(days=32)).replace(day=1)
        end_month = next_month - timedelta(days=1)
        start_dt = datetime.combine(start_month, datetime.min.time())
        end_dt = datetime.combine(end_month, datetime.max.time())
        trunc_expr = TruncWeek("created_at")

    # === Filter booking CONFIRMED dalam range waktu ===
    confirmed_bookings = Booking.objects.filter(
        status="CONFIRMED",
        created_at__range=[start_dt, end_dt]
    )

    # === Total Pendapatan ===
    revenue_data = (
        confirmed_bookings
        .annotate(period=trunc_expr)
        .values("period")
        .annotate(total_revenue=Sum("total_price"))
        .order_by("period")
    )

    # === Total Tiket Terjual ===
    ticket_trunc = TruncDay("booking__created_at") if period in ["daily", "weekly"] else TruncWeek("booking__created_at")

    tickets_data = (
        Ticket.objects.filter(
            booking__status="CONFIRMED",
            booking__created_at__range=[start_dt, end_dt]
        )
        .annotate(period=ticket_trunc)
        .values("period")
        .annotate(tickets_sold=Count("ticket_id"))
        .order_by("period")
    )

    # === Format Output ===
    revenue_list, tickets_list = [], []

    if period == "daily":
        label = today.strftime("%d/%m/%Y")
        total_rev = revenue_data[0]["total_revenue"] if revenue_data else 0
        total_tix = tickets_data[0]["tickets_sold"] if tickets_data else 0
        revenue_list.append({"date": label, "total_revenue": float(total_rev)})
        tickets_list.append({"date": label, "tickets_sold": total_tix})

    elif period == "weekly":
        days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        rev_map = {r["period"].date(): float(r["total_revenue"] or 0) for r in revenue_data}
        tix_map = {t["period"].date(): t["tickets_sold"] for t in tickets_data}

        for i in range(7):
            d = start_dt.date() + timedelta(days=i)
            revenue_list.append({"date": days[i], "total_revenue": rev_map.get(d, 0.0)})
            tickets_list.append({"date": days[i], "tickets_sold": tix_map.get(d, 0)})

    else:  # monthly
        for idx in range(1, 5):
            rev_val = float(revenue_data[idx - 1]["total_revenue"]) if idx - 1 < len(revenue_data) else 0.0
            tix_val = tickets_data[idx - 1]["tickets_sold"] if idx - 1 < len(tickets_data) else 0
            revenue_list.append({"date": f"Minggu {idx}", "total_revenue": rev_val})
            tickets_list.append({"date": f"Minggu {idx}", "tickets_sold": tix_val})

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
    return render(request, "user_analytics.html")


@login_required
@user_passes_test(is_user)
def api_user_analytics_data(request):
    """API untuk data User Analytics"""
    period = request.GET.get("period", "daily").lower()
    today = now().date()

    bookings = Booking.objects.filter(
        user=request.user,
        status="CONFIRMED",
        created_at__isnull=False
    )

    # === Filter per periode ===
    if period == "daily":
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())
        trunc_field = TruncDay("created_at")

    elif period == "weekly":
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)
        start_dt = datetime.combine(start_week, datetime.min.time())
        end_dt = datetime.combine(end_week, datetime.max.time())
        trunc_field = TruncDay("created_at")

    else:  # monthly
        start_month = today.replace(day=1)
        next_month = (start_month + timedelta(days=32)).replace(day=1)
        end_month = next_month - timedelta(days=1)
        start_dt = datetime.combine(start_month, datetime.min.time())
        end_dt = datetime.combine(end_month, datetime.max.time())
        trunc_field = ExtractWeek("created_at")

    bookings = bookings.filter(created_at__range=[start_dt, end_dt])

    # === Total Pengeluaran ===
    spending_data = (
        bookings.annotate(period=trunc_field)
        .values("period")
        .annotate(total_spent=Sum("total_price"))
        .order_by("period")
    )

    # === Format Data ===
    spending_list = []
    if period == "daily":
        total = spending_data[0]["total_spent"] if spending_data else 0
        spending_list.append({
            "date": today.strftime("%d/%m/%Y"),
            "total_spent": float(total)
        })
    elif period == "weekly":
        day_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
        data_map = {item["period"].date(): float(item["total_spent"] or 0) for item in spending_data}
        for i in range(7):
            d = start_dt.date() + timedelta(days=i)
            spending_list.append({
                "date": day_names[i],
                "total_spent": data_map.get(d, 0.0)
            })
    else:
        for idx in range(1, 5):
            val = float(spending_data[idx - 1]["total_spent"]) if idx - 1 < len(spending_data) else 0.0
            spending_list.append({"date": f"Minggu {idx}", "total_spent": val})

    # === Seat Count ===
    tickets = Ticket.objects.filter(booking__in=bookings).select_related("ticket_type")
    seat_count = (
        tickets.values("ticket_type__seat_category")
        .annotate(count=Count("ticket_id"))
        .order_by("ticket_type__seat_category")
    )

    # === Kehadiran ===
    total_matches = Match.objects.filter(
        ticket_prices__ticket__booking__user=request.user,
        ticket_prices__ticket__booking__status="CONFIRMED"
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
