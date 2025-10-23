from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count, F
from django.db.models.functions import ExtractMonth, ExtractYear
from bookings.models import Booking, Ticket
from matches.models import Match, TicketPrice


# === ROLE CHECKERS ===
def is_admin(user):
    return user.is_authenticated and getattr(user, "role", None) == "admin"

def is_user(user):
    return user.is_authenticated and getattr(user, "role", None) == "user"


# =====================================
# ==== ADMIN ANALYTICS PAGE ===========
# =====================================

@login_required
@user_passes_test(is_admin)
def admin_analytics_page(request):
    matches = Match.objects.all().order_by("-date")
    seat_categories = ["ALL", "VVIP", "VIP", "REGULAR"]
    return render(request, "reviews/admin_analytics.html", {
        "matches": matches,
        "seat_categories": seat_categories,
    })


@login_required
@user_passes_test(is_admin)
def api_admin_analytics_data(request):
    match_id = request.GET.get("match_id")
    seat_filter = request.GET.get("seat")

    tickets = Ticket.objects.select_related("ticket_type__match").all()

    if match_id:
        tickets = tickets.filter(ticket_type__match__id=match_id)
    if seat_filter and seat_filter != "ALL":
        tickets = tickets.filter(ticket_type__seat_category=seat_filter)

    revenue_data = (
        tickets.values(
            "ticket_type__match__id",
            "ticket_type__match__home_team__name",
            "ticket_type__match__away_team__name"
        )
        .annotate(
            tickets_sold=Count("id", distinct=True),
            total_revenue=Sum(F("ticket_type__price")),
        )
        .order_by("ticket_type__match__date")
    )

    occupancy_data = []
    ticket_prices = TicketPrice.objects.select_related("match").all()
    for tp in ticket_prices:
        sold = tickets.filter(ticket_type=tp).count()
        occupancy = (sold / tp.quantity_available * 100) if tp.quantity_available else 0
        occupancy_data.append({
            "matchId": str(tp.match.id),
            "matchName": f"{tp.match.home_team.name} vs {tp.match.away_team.name}",
            "seatCategory": tp.seat_category,
            "occupancy": round(occupancy, 2),
        })

    return JsonResponse({
        "revenueData": list(revenue_data),
        "occupancyData": occupancy_data,
    })


# =====================================
# ==== USER ANALYTICS PAGE ============
# =====================================

@login_required
@user_passes_test(is_user)
def user_analytics_page(request):
    return render(request, "reviews/user_analytics.html")


@login_required
@user_passes_test(is_user)
def api_user_analytics_data(request):
    bookings = Booking.objects.filter(
        user=request.user, 
        status="CONFIRMED",
        created_at__isnull=False
    ).order_by("created_at")

    spending_data = (
        bookings
        .annotate(month=ExtractMonth("created_at"), year=ExtractYear("created_at"))
        .values("month", "year")
        .annotate(total_spent=Sum("total_price"))
        .order_by("year", "month")
    )

    tickets = Ticket.objects.filter(booking__in=bookings).select_related("ticket_type")
    seat_count = (
        tickets.values("ticket_type__seat_category")
        .annotate(count=Count("ticket_id"))
        .order_by("ticket_type__seat_category")
    )

    return JsonResponse({
        "spendingData": list(spending_data),
        "seatCount": list(seat_count),
    })
