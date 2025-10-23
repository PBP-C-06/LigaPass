from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, ExtractDay, ExtractMonth, ExtractYear
from bookings.models import Booking, Ticket
from matches.models import Match, TicketPrice
from reviews.models import Review


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
    """
    Halaman Analytics untuk Admin — menampilkan total tiket terjual dan total pendapatan kumulatif
    (tidak dibedakan per pertandingan).
    """
    return render(request, "reviews/admin_analytics.html")


@login_required
@user_passes_test(is_admin)
def api_admin_analytics_data(request):
    """
    API untuk admin analytics — mengembalikan:
    - ticketsData: total tiket terjual per periode (daily/weekly/monthly)
    - revenueData: total pendapatan per periode (daily/weekly/monthly)
    """
    period = request.GET.get("period", "monthly").lower()

    # Tentukan granularity
    if period == "daily":
        trunc = TruncDay("created_at")
    elif period == "weekly":
        trunc = TruncWeek("created_at")
    else:
        trunc = TruncMonth("created_at")

    # Booking yang dikonfirmasi
    confirmed_bookings = Booking.objects.filter(status="CONFIRMED")

    # === Total Pendapatan ===
    revenue_data = (
        confirmed_bookings
        .annotate(period=trunc)
        .values("period")
        .annotate(total_revenue=Sum("total_price"))
        .order_by("period")
    )

    # === Total Tiket Terjual ===
    tickets_data = (
        Ticket.objects.filter(booking__status="CONFIRMED")
        .annotate(period=trunc)
        .values("period")
        .annotate(tickets_sold=Count("ticket_id"))
        .order_by("period")
    )

    # Format ke JSON
    revenue_list = [
        {
            "date": r["period"].strftime("%Y-%m-%d") if r["period"] else None,
            "total_revenue": float(r["total_revenue"] or 0),
        }
        for r in revenue_data
    ]

    tickets_list = [
        {
            "date": t["period"].strftime("%Y-%m-%d") if t["period"] else None,
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
    """
    Halaman Analytics untuk User — menampilkan pengeluaran, seat category, dan kehadiran.
    """
    return render(request, "reviews/user_analytics.html")


@login_required
@user_passes_test(is_user)
def api_user_analytics_data(request):
    """
    API untuk user analytics:
    - spendingData: total pengeluaran per hari
    - seatCount: jumlah tiket per kategori
    - attendance: perbandingan match yang direview vs belum
    """
    bookings = Booking.objects.filter(
        user=request.user,
        status="CONFIRMED",
        created_at__isnull=False
    ).order_by("created_at")

    # === Total Pengeluaran per Hari ===
    spending_data = (
        bookings
        .annotate(
            day=ExtractDay("created_at"),
            month=ExtractMonth("created_at"),
            year=ExtractYear("created_at"),
        )
        .values("day", "month", "year")
        .annotate(total_spent=Sum("total_price"))
        .order_by("year", "month", "day")
    )

    spending_data = [
        {
            "date": f"{item['day']:02d}/{item['month']:02d}/{item['year']}",
            "total_spent": float(item["total_spent"]),
        }
        for item in spending_data
    ]

    # === Jumlah Tiket per Kategori ===
    tickets = Ticket.objects.filter(booking__in=bookings).select_related("ticket_type")
    seat_count = (
        tickets.values("ticket_type__seat_category")
        .annotate(count=Count("id"))
        .order_by("ticket_type__seat_category")
    )

    # === Statistik Kehadiran (berdasarkan review) ===
    total_matches = Match.objects.filter(
        ticket_prices__ticket__booking__user=request.user
    ).distinct().count()

    reviewed_matches = Review.objects.filter(user=request.user).count()
    attendance = {
        "hadir": reviewed_matches,
        "tidak_hadir": max(total_matches - reviewed_matches, 0)
    }

    return JsonResponse({
        "spendingData": spending_data,
        "seatCount": list(seat_count),
        "attendance": attendance,
    })
