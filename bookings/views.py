from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from bookings.models import *
from matches.models import *
from django.utils import timezone
import requests, json
from django.views.decorators.csrf import csrf_exempt
# Create your views here.

def create_booking(request, match_id):
    match = get_object_or_404(Match, id=match_id)
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
        booking_items = []

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
            booking_items.append((ticket_type, quantity))
        
        booking = Booking.objects.create(
            user=request.user
        )
        
        for ticket_type, qty in booking_items:
            BookingItem.objects.create(
                booking=booking,
                ticket_type=ticket_type,
                quantity=qty
            )

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

@csrf_exempt
def midtrans_notification(request):
    # Midtrans hanya mengirimkan POST request
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        payload = json.loads(request.body)
        order_id = payload.get('order_id')
        if not order_id:
            return JsonResponse({'error': 'Missing order_id'}, status=400)

        # --- Verifikasi ke Midtrans ---
        url = f"https://api.sandbox.midtrans.com/v2/{order_id}/status"
        auth = (settings.MIDTRANS_SERVER_KEY, '')
        r = requests.get(url, auth=auth)
        status_data = r.json()
        transaction_status = status_data.get("transaction_status")
        fraud_status = status_data.get("fraud_status")

        # --- Ambil booking ---
        booking = Booking.objects.filter(midtrans_order_id=order_id).first()
        if not booking:
            return JsonResponse({'error': 'Booking not found'}, status=404)

        # --- Update payment status ---
        if transaction_status in ['settlement', 'capture'] and fraud_status == 'accept':
            booking.status = 'CONFIRMED'
            booking.updated_at = timezone.now()
            booking.save(update_fields=['status', 'updated_at'])

            tickets_created = []

            # Generate tiket sesuai jumlah di BookingItem
            for item in booking.items.all():
                for _ in range(item.quantity):
                    t = Ticket.objects.create(
                        booking=booking,
                        ticket_type=item.ticket_type
                    )
                    tickets_created.append({
                        "ticket_id": str(t.ticket_id),
                        "seat_category": item.ticket_type.seat_category,
                        "match_id": str(item.ticket_type.match.id),
                    })

            return JsonResponse({
                'message': 'Payment verified and tickets generated',
                'order_id': order_id,
                'booking_id': str(booking.booking_id),
                'status': booking.status,
                'tickets': tickets_created
            }, status=200)

        # Pembayaran gagal 
        elif transaction_status in ['expire', 'cancel', 'deny']:
            # Balikin stok tiket
            for item in booking.items.all():
                item.ticket_type.quantity_available += item.quantity
                item.ticket_type.save(update_fields=["quantity_available"])

            booking.status = 'EXPIRED' if transaction_status == 'expire' else 'CANCELLED'
            booking.updated_at = timezone.now()
            booking.save(update_fields=['status', 'updated_at'])

            return JsonResponse({
                'message': f'Payment {transaction_status}, stock restored.',
                'booking_id': str(booking.booking_id),
                'status': booking.status
            }, status=200)

        # =============================
        # 🕒 MASIH PENDING
        # =============================
        else:
            booking.status = 'PENDING'
            booking.updated_at = timezone.now()
            booking.save(update_fields=['status', 'updated_at'])

            return JsonResponse({
                'message': f'Transaction still pending ({transaction_status})',
                'booking_id': str(booking.booking_id),
                'status': booking.status
            }, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)