from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from bookings.models import *
from matches.models import *
import requests, base64, json
# Create your views here.

def create_booking(request, match_id):
    match = get_object_or_404(Match, api_id=match_id)
    if request.method == "GET":
        ticket_prices = TicketPrice.objects.filter(match=match)
        return render(request, "create_booking.html", {
            "match": match,
            "ticket_prices": ticket_prices,
        })
    
    elif request.method == "POST":
        data = json.loads(request.body)
        ticket_types = data.get("types", {})
        total_price = 0
        tickets = []

        for seat_category, quantity in ticket_types.items():
            ticket_type = get_object_or_404(TicketPrice, match=match, seat_category=seat_category)

            if ticket_type.quantity_available < quantity:
                return JsonResponse(
                    {"error": f"Not enough tickets available for {seat_category}"},
                    status=400
                )

            total_price += ticket_type.price * quantity
            ticket_type.quantity_available -= quantity
            ticket_type.save()
            tickets.append((ticket_type, quantity))
        
        booking = Booking.objects.create(
            user=request.user,
            total_price=total_price
        )

        for ticket_type, qty in tickets:
            for _ in range(qty):
                Ticket.objects.create(booking=booking, ticket_type=ticket_type)

        return JsonResponse({
            "message": "Booking created successfully",
            "booking_id": str(booking.booking_id),
            "total_price": float(total_price),
        }, status=201)
    return JsonResponse({"error": "Invalid request method"}, status=405)

def payment(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id)
    if request.method == "GET":
        return render(request, "payment.html", {
            "booking": booking,
            "MIDTRANS_CLIENT_KEY": settings.MIDTRANS_CLIENT_KEY
        })
    elif request.method == "POST":
        data = json.loads(request.body)
        token_id = data.get("token_id")

        if not token_id:
            return JsonResponse({"error": "Missing token_id"}, status=400)

        # Basic Auth Midtrans pakai Server Key
        server_key = settings.MIDTRANS_SERVER_KEY
        auth_str = base64.b64encode(f"{server_key}:".encode()).decode()

        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "payment_type": "credit_card",
            "transaction_details": {
                "order_id": f"booking-{booking.booking_id}",
                "gross_amount": float(booking.total_price),
            },
            "credit_card": {
                "token_id": token_id,
                "authentication": True,
            },
            "customer_details": {
                "first_name": booking.user.username,
                "email": booking.user.email or "noemail@example.com",
            },
        }

        response = requests.post(
            "https://api.sandbox.midtrans.com/v2/charge",
            headers=headers,
            json=payload,
        )

        result = response.json()
        print("[MIDTRANS RESPONSE]", result)

        if response.status_code == 201 and "redirect_url" in result:
            booking.midtrans_order_id = result.get("order_id")
            booking.save(update_fields=["midtrans_order_id"])
            return JsonResponse({"redirect_url": result["redirect_url"]}, status=200)

        return JsonResponse(result, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=405)
# def payment(request, booking_id):
#     booking = get_object_or_404(Booking, booking_id=booking_id)
#     if request.method == "GET":
#         # Buat Snap token
#         server_key = settings.MIDTRANS_SERVER_KEY
#         auth_str = base64.b64encode(f"{server_key}:".encode()).decode()

#         headers = {
#             "Authorization": f"Basic {auth_str}",
#             "Content-Type": "application/json",
#         }

#         payload = {
#             "transaction_details": {
#                 "order_id": f"booking-{booking.booking_id}",
#                 "gross_amount": float(booking.total_price),
#             },
#             "credit_card": {
#                 "secure": True
#             },
#             "customer_details": {
#                 "first_name": booking.user.username,
#                 "email": booking.user.email or "noemail@example.com",
#             },
#         }

#         response = requests.post(
#             "https://app.sandbox.midtrans.com/snap/v1/transactions",
#             headers=headers,
#             json=payload,
#         )

#         snap_data = response.json()
#         snap_token = snap_data.get("token")

#         return render(request, "payment_snap.html", {
#             "booking": booking,
#             "SNAP_TOKEN": snap_token,
#             "MIDTRANS_CLIENT_KEY": settings.MIDTRANS_CLIENT_KEY
#         })

def ticket(request):
    return None