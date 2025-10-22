from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Count, F
from bookings.models import Booking, Ticket
from matches.models import Match, TicketPrice

# === ROLE CHECKERS ===
def is_admin(user):
    return user.is_authenticated and user.role == "admin"

def is_user(user):
    return user.is_authenticated and user.role == "user"


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
    """
    Return JSON for:
    - total revenue per match
    - tickets sold per match
    - seat occupancy per category
    """
    match_id = request.GET.get("match_id")
    seat_filter = request.GET.get("seat")

    tickets = Ticket.objects.select_related("ticket_type__match")

    if match_id:
        tickets = tickets.filter(ticket_type__match__id=match_id)
    if seat_filter and seat_filter != "ALL":
        tickets = tickets.filter(ticket_type__seat_category=seat_filter)

    # total revenue (sum of ticket_type.price)
    revenue_data = (
        tickets.values("ticket_type__match__id", "ticket_type__match__home_team__name", "ticket_type__match__away_team__name")
        .annotate(
            total_revenue=Sum("ticket_type__price"),
            tickets_sold=Count("id"),
        )
        .order_by("ticket_type__match__id")
    )

    # seat occupancy (sold / available)
    occupancy_data = []
    ticket_prices = TicketPrice.objects.all()
    for tp in ticket_prices:
        sold = tickets.filter(ticket_type=tp).count()
        occupancy = 0
        if tp.quantity_available > 0:
            occupancy = (sold / tp.quantity_available) * 100
        occupancy_data.append({
            "match": str(tp.match.id),
            "seat_category": tp.seat_category,
            "occupancy": round(occupancy, 2)
        })

    return JsonResponse({
        "revenue_data": list(revenue_data),
        "occupancy_data": occupancy_data,
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
    """
    Return JSON for:
    - total spending per month
    - count of tickets by seat category
    """
    bookings = Booking.objects.filter(user=request.user, status="CONFIRMED").order_by("created_at")

    # spending per month
    spending_data = (
        bookings.annotate(month=F("created_at__month"))
        .values("month")
        .annotate(total_spent=Sum("total_price"))
        .order_by("month")
    )

    # ticket distribution by category
    tickets = Ticket.objects.filter(booking__in=bookings).select_related("ticket_type")
    seat_count = (
        tickets.values("ticket_type__seat_category")
        .annotate(count=Count("id"))
        .order_by("ticket_type__seat_category")
    )

    return JsonResponse({
        "spending_data": list(spending_data),
        "seat_count": list(seat_count),
    })
