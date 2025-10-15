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
        import uuid, json, base64, requests
        data = json.loads(request.body)
        method = data.get("method")
        token_id = data.get("token_id")
        bank = data.get("bank")

        # --- AUTH ---
        server_key = settings.MIDTRANS_SERVER_KEY
        auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # --- ORDER ID ---
        order_id = f"booking-{method}-{uuid.uuid4().hex[:10]}"

        # --- PAYLOAD ---
        payload = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": float(booking.total_price),
            },
            "customer_details": {
                "first_name": booking.user.username,
                "email": booking.user.email,
            },
        }

        # Payment type
        if method == "card":
            payload["payment_type"] = "credit_card"
            payload["credit_card"] = {
                "token_id": token_id,
                "authentication": True
            }
        elif method == "bank":
            payload["payment_type"] = "bank_transfer"
            payload["bank_transfer"] = {"bank": bank}
        elif method == "gopay":
            payload["payment_type"] = "gopay"
            payload["gopay"] = {
                "enable_callback": True,
                "callback_url": request.build_absolute_uri('/payment/finish/')
            }
        else:
            return JsonResponse({"error": "Invalid method"}, status=400)

        # --- SEND TO MIDTRANS ---
        response = requests.post(
            "https://api.sandbox.midtrans.com/v2/charge",
            headers=headers,
            json=payload
        )

        # Simpan order_id di booking
        booking.midtrans_order_id = order_id
        booking.save(update_fields=["midtrans_order_id"])

        # --- Return langsung semua respons Midtrans ke FE ---
        return JsonResponse(response.json(), status=response.status_code)


def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id)

    if booking.status == "PENDING":  # hanya cancel jika belum dibayar
        booking.status = "CANCELLED"
        booking.save(update_fields=["status"])
        return JsonResponse({"message": "Booking cancelled due to timeout"})

    return JsonResponse({"message": "Booking already processed"}, status=400)

def ticket(request):
    return None