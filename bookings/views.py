from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from bookings.models import *
from matches.models import *
import requests, json, base64, uuid


@login_required
def create_booking(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    # GET: tampilkan halaman pemesanan
    if request.method == "GET":
        ticket_prices = TicketPrice.objects.filter(match=match).order_by('price')
        return render(request, "create_booking.html", {
            "match": match,
            "ticket_prices": ticket_prices,
        })

    # POST: buat booking baru
    elif request.method == "POST":
        data = json.loads(request.body)
        ticket_types = data.get("types", {})
        method = data.get("method")
        total_price = 0
        booking_items = []

        if not ticket_types:
            return JsonResponse({"error": "No tickets selected"}, status=400)
        if not method:
            return JsonResponse({"error": "Payment method not selected"}, status=400)

        # Hitung total dan validasi stok
        for seat_category, quantity in ticket_types.items():
            try:
                ticket_type = TicketPrice.objects.get(match=match, seat_category=seat_category)
            except TicketPrice.DoesNotExist:
                return JsonResponse({"error": f"Ticket type {seat_category} not found"}, status=404)

            quantity = int(quantity)
            if quantity <= 0:
                continue

            if ticket_type.quantity_available < quantity:
                return JsonResponse(
                    {"error": f"Not enough tickets available for {seat_category}"},
                    status=400
                )

            total_price += ticket_type.price * quantity
            ticket_type.quantity_available -= quantity
            ticket_type.save()
            booking_items.append((ticket_type, quantity))

        if not booking_items:
            return JsonResponse({"error": "No valid tickets selected"}, status=400)

        # Buat booking
        booking = Booking.objects.create(
            user=request.user,
            total_price=total_price,
            status='PENDING'
        )

        # Simpan tiap item booking
        for ticket_type, qty in booking_items:
            BookingItem.objects.create(
                booking=booking,
                ticket_type=ticket_type,
                quantity=qty
            )

        # Simpan metode pembayaran ke session
        request.session["selected_method"] = method
        request.session.modified = True

        return JsonResponse({
            "message": "Booking created successfully",
            "booking_id": str(booking.booking_id),
            "total_price": float(total_price),
        }, status=201)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@login_required
def payment(request, booking_id):
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)

    if request.method == "GET":
        selected_method = request.session.get("selected_method")
        return render(request, "payment.html", {
            "booking": booking,
            "MIDTRANS_CLIENT_KEY": settings.MIDTRANS_CLIENT_KEY,
            "selected_method": selected_method
        })

    elif request.method == "POST":
        data = json.loads(request.body)
        method = data.get("method")
        token_id = data.get("token_id")

        if not method:
            return JsonResponse({"error": "Payment method is required"}, status=400)

        # Setup authorization Midtrans
        server_key = settings.MIDTRANS_SERVER_KEY
        auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Cek apakah transaksi sebelumnya sudah dibuat
        if booking.midtrans_order_id:
            payment_responses = request.session.get("payment_responses", {})
            cached = payment_responses.get(str(booking.booking_id))
            if cached:
                return JsonResponse(cached)
            else:
                check_res = requests.get(
                    f"https://api.sandbox.midtrans.com/v2/{booking.midtrans_order_id}/status",
                    headers=headers
                )
                return JsonResponse(check_res.json(), status=check_res.status_code)

        if booking.status != 'PENDING':
            return JsonResponse({"error": "Booking already processed"}, status=400)

        order_id = f"book-{method[:3]}-{uuid.uuid4().hex[:8]}"

        # Siapkan detail item
        item_details = [{
            "id": str(item.id),
            "price": float(item.ticket_type.price),
            "quantity": item.quantity,
            "name": f"Ticket {item.ticket_type.seat_category}"
        } for item in booking.items.all()]

        payload = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": int(booking.total_price),
            },
            "customer_details": {
                "first_name": booking.user.first_name or booking.user.username,
                "last_name": booking.user.last_name or "",
                "email": booking.user.email,
                "phone": getattr(getattr(booking.user, "profile", None), "phone_number", ""),
            },
            "item_details": item_details,
        }

        # Tentukan payment type
        if method == "card":
            if not token_id:
                return JsonResponse({"error": "Card token is required"}, status=400)
            payload["payment_type"] = "credit_card"
            payload["credit_card"] = {"token_id": token_id, "authentication": True}
        elif method.startswith("bank_"):
            bank = method.split("_")[1]
            if bank not in ["bca", "bni", "bri", "cimb", "mandiri"]:
                return JsonResponse({"error": "Invalid bank"}, status=400)
            payload["payment_type"] = "bank_transfer"
            payload["bank_transfer"] = {"bank": bank}
        elif method == "gopay":
            payload["payment_type"] = "qris"
            payload["qris"] = {"acquirer": "gopay"}
        else:
            return JsonResponse({"error": "Invalid payment method"}, status=400)

        # Kirim request ke Midtrans
        try:
            res = requests.post("https://api.sandbox.midtrans.com/v2/charge",
                                headers=headers, json=payload, timeout=20)
            mid_data = res.json()
            if res.status_code >= 400:
                return JsonResponse(mid_data, status=res.status_code)
        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"Midtrans request failed: {e}"}, status=500)

        # Cache response di session
        payment_responses = request.session.get("payment_responses", {})
        payment_responses[str(booking.booking_id)] = mid_data
        request.session["payment_responses"] = payment_responses
        request.session.modified = True

        booking.midtrans_order_id = order_id
        booking.status = mid_data.get("transaction_status", "PENDING").upper()
        booking.save(update_fields=["midtrans_order_id", "status"])

        return JsonResponse(mid_data)

    return JsonResponse({"error": "Invalid method"}, status=405)

def cancel_booking(request, booking_id):
    # Pastikan booking milik user dan masih pending
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)

    if booking.status == "PENDING":
        if booking.midtrans_order_id:
             try:
                 cancel_url = f"https://api.sandbox.midtrans.com/v2/{booking.midtrans_order_id}/cancel"
                 server_key = settings.MIDTRANS_SERVER_KEY
                 auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
                 headers = {"Authorization": f"Basic {auth_str}", "Accept": "application/json"}
                 cancel_res = requests.post(cancel_url, headers=headers)
                 if cancel_res.status_code != 200:
                      print(f"Midtrans cancel failed: {cancel_res.text}")
             except Exception as e:
                 print(f"Midtrans cancel request failed: {e}")

        # Kembalikan stok
        for item in booking.items.all():
            item.ticket_type.quantity_available += item.quantity
            item.ticket_type.save(update_fields=["quantity_available"])

        booking.status = "CANCELLED"
        booking.save(update_fields=["status"])

        # HAPUS DATA SESSION
        if "payment_responses" in request.session:
            if str(booking.booking_id) in request.session["payment_responses"]:
                del request.session["payment_responses"][str(booking.booking_id)]
                request.session.modified = True

        return JsonResponse({"message": "Booking cancelled successfully"})

    return JsonResponse({"message": f"Booking cannot be cancelled (Status: {booking.status})"}, status=400)

@login_required
def check_booking_status(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id, user=request.user)
        return JsonResponse({"status": booking.status})
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)


@csrf_exempt
def midtrans_notification(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        print("Raw body bytes:", request.body)
        print("Decoded body:", request.body.decode('utf-8', errors='ignore'))
        payload = json.loads(request.body)
        order_id = payload.get("order_id")
        if not order_id:
            return JsonResponse({'error': 'Missing order_id'}, status=400)

        transaction_status = payload.get("transaction_status")
        fraud_status = payload.get("fraud_status")

        booking = Booking.objects.filter(midtrans_order_id=order_id).first()
        if not booking:
            return JsonResponse({'message': 'Booking not found'}, status=200)

        new_status = None
        if transaction_status in ["settlement", "capture"] and fraud_status == "accept":
            new_status = "CONFIRMED"
            for item in booking.items.all():
                for _ in range(item.quantity):
                    Ticket.objects.create(booking=booking, ticket_type=item.ticket_type)
        elif transaction_status in ["expire", "cancel", "deny"]:
            new_status = "EXPIRED" if transaction_status == "expire" else "CANCELLED"
            for item in booking.items.all():
                item.ticket_type.quantity_available += item.quantity
                item.ticket_type.save()

        if new_status:
            booking.status = new_status
            booking.updated_at = timezone.now()
            booking.save(update_fields=["status", "updated_at"])

        return JsonResponse({'message': f'Processed {order_id} with {booking.status}'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
