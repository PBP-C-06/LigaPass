from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from bookings.models import *
from matches.models import *
from django.utils import timezone
import requests, json, base64, uuid
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required


@login_required
def create_booking(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    # --- GET: render halaman pilih kursi & metode ---
    if request.method == "GET":
        ticket_prices = TicketPrice.objects.filter(match=match).order_by('price')
        return render(request, "create_booking.html", {
            "match": match,
            "ticket_prices": ticket_prices,
        })

    # --- POST: buat booking baru ---
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

        # Hitung total dan kurangi stok tiket
        for seat_category, quantity in ticket_types.items():
            try:
                ticket_type = TicketPrice.objects.get(match=match, seat_category=seat_category)
            except TicketPrice.DoesNotExist:
                 return JsonResponse({"error": f"Ticket type {seat_category} not found"}, status=404)

            quantity = int(quantity)
            if quantity <= 0: continue

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

        booking = Booking.objects.create(
            user=request.user,
            total_price=total_price,
            status='PENDING'
        )

        # Simpan item booking
        for ticket_type, qty in booking_items:
            BookingItem.objects.create(
                booking=booking,
                ticket_type=ticket_type,
                quantity=qty
            )

        # Simpan metode pembayaran sementara ke session (biar diambil di payment)
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
        selected_method = request.session.get("selected_method", None)
        if not selected_method and booking.status == 'PENDING' and not booking.midtrans_order_id:
            pass

        return render(request, "payment.html", {
            "booking": booking,
            "MIDTRANS_CLIENT_KEY": settings.MIDTRANS_CLIENT_KEY,
            "selected_method": selected_method
        })

    # --- POST: buat transaksi ke Midtrans ---
    elif request.method == "POST":
        data = json.loads(request.body)
        method = data.get("method")
        token_id = data.get("token_id")

        if not method:
            return JsonResponse({"error": "Payment method is required"}, status=400)

        # --- AUTH BASIC ---
        server_key = settings.MIDTRANS_SERVER_KEY
        auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if booking.midtrans_order_id:
            payment_responses = request.session.get("payment_responses", {})
            stored_response = payment_responses.get(str(booking.booking_id))

            if stored_response:
                return JsonResponse(stored_response, status=200)
            else:
                check_url = f"https://api.sandbox.midtrans.com/v2/{booking.midtrans_order_id}/status"
                check_res = requests.get(check_url, headers=headers)
                check_data = check_res.json()
                return JsonResponse(check_data, status=check_res.status_code)

        # Pastikan booking masih PENDING sebelum membuat order baru
        if booking.status != 'PENDING':
            return JsonResponse({"error": "Booking is already processed or expired"}, status=400)

        order_id = f"book-{method[:3]}-{uuid.uuid4().hex[:8]}"

        item_details = []
        for item in booking.items.all():
            item_details.append({
                "id": str(item.id),
                "price": float(item.ticket_type.price),
                "quantity": item.quantity,
                "name": f"Ticket: {item.ticket_type.seat_category}" 
            })

        payload = {
            "transaction_details": {
                "order_id": order_id,
                "gross_amount": int(booking.total_price),
            },
            "customer_details": {
                "first_name": booking.user.first_name or booking.user.username,
                "last_name": booking.user.last_name or "",
                "email": booking.user.email,
                "phone":booking.user.profile.phone_number if hasattr(booking.user, 'profile') else "",
            },
            "item_details": item_details
        }

        if method == "card":
            if not token_id:
                 return JsonResponse({"error": "Card token is required"}, status=400)
            payload["payment_type"] = "credit_card"
            payload["credit_card"] = {
                "token_id": token_id,
                "authentication": True
            }

        elif method.startswith("bank_"):
            bank_name = method.split("_")[1]
            # Validasi bank name jika perlu
            if bank_name not in ['bca', 'bni', 'bri', 'cimb']:
                 return JsonResponse({"error": f"Invalid bank: {bank_name}"}, status=400)
            payload["payment_type"] = "bank_transfer"
            payload["bank_transfer"] = {"bank": bank_name}

        elif method == "gopay":
            payload["payment_type"] = "qris"
            payload["qris"] = {"acquirer": "gopay"}

        else:
            return JsonResponse({"error": f"Invalid payment method: {method}"}, status=400)

        # --- KIRIM REQUEST KE MIDTRANS ---
        try:
            response = requests.post(
                "https://api.sandbox.midtrans.com/v2/charge",
                headers=headers,
                json=payload,
                timeout=20
            )
            midtrans_data = response.json()

            # Tangani error dari Midtrans
            if response.status_code >= 400:
                return JsonResponse(midtrans_data, status=response.status_code)

        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": f"Midtrans request failed: {e}"}, status=500)

        if "payment_responses" not in request.session:
            request.session["payment_responses"] = {}
        request.session["payment_responses"][str(booking.booking_id)] = midtrans_data
        request.session.modified = True

        booking.midtrans_order_id = order_id
        booking.status = midtrans_data.get("transaction_status", "PENDING").upper()
        booking.save(update_fields=["midtrans_order_id", "status"])

        return JsonResponse(midtrans_data, status=response.status_code)

    return JsonResponse({"error": "Invalid request method"}, status=405)

def cancel_booking(request, booking_id):
    # Pastikan booking milik user dan masih pending
    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)

    if booking.status == "PENDING":
        # Idealnya panggil API Cancel Midtrans jika sudah ada order_id
        if booking.midtrans_order_id:
             try:
                 cancel_url = f"https://api.sandbox.midtrans.com/v2/{booking.midtrans_order_id}/cancel"
                 server_key = settings.MIDTRANS_SERVER_KEY
                 auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
                 headers = {"Authorization": f"Basic {auth_str}", "Accept": "application/json"}
                 cancel_res = requests.post(cancel_url, headers=headers)
                 if cancel_res.status_code != 200:
                      print(f"Midtrans cancel failed: {cancel_res.text}")
                      # Tetap lanjutkan proses cancel di sisi kita
             except Exception as e:
                 print(f"Midtrans cancel request failed: {e}")

        # Kembalikan stok
        for item in booking.items.all():
            item.ticket_type.quantity_available += item.quantity
            item.ticket_type.save(update_fields=["quantity_available"])

        booking.status = "CANCELLED" # Lebih tepat 'CANCELLED' daripada 'EXPIRED'
        booking.save(update_fields=["status"])

        # Hapus data sesi terkait booking ini
        if "payment_responses" in request.session:
            if str(booking.booking_id) in request.session["payment_responses"]:
                del request.session["payment_responses"][str(booking.booking_id)]
                request.session.modified = True

        return JsonResponse({"message": "Booking cancelled successfully"})

    return JsonResponse({"message": f"Booking cannot be cancelled (Status: {booking.status})"}, status=400)


@csrf_exempt
def midtrans_notification(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid method'}, status=405)

    try:
        payload = json.loads(request.body)
        order_id = payload.get('order_id')
        if not order_id:
            return JsonResponse({'error': 'Missing order_id'}, status=400)

        transaction_status = payload.get("transaction_status")
        fraud_status = payload.get("fraud_status")

        booking = Booking.objects.filter(midtrans_order_id=order_id).first()
        if not booking:
            # Penting: Kirim status 200 agar Midtrans tidak retry
            print(f"Webhook received for unknown order_id: {order_id}")
            return JsonResponse({'message': 'Booking not found, notification ignored'}, status=200)

        if booking.status == 'PENDING':
            new_status = None
            if transaction_status in ['settlement', 'capture'] and fraud_status == 'accept':
                new_status = 'CONFIRMED'

                # Pindahkan logika create ticket ke sini
                tickets_created = []
                for item in booking.items.all():
                    for _ in range(item.quantity):
                        t = Ticket.objects.create(
                            booking=booking,
                            ticket_type=item.ticket_type
                            # Tambah field unik jika perlu (misal seat number)
                        )
                        tickets_created.append({"ticket_id": str(t.ticket_id)})
                print(f"Tickets created for booking {booking.booking_id}: {tickets_created}")


            elif transaction_status in ['expire', 'cancel', 'deny']:
                new_status = 'EXPIRED' if transaction_status == 'expire' else 'CANCELLED'

                # Kembalikan stok HANYA jika status baru adalah EXPIRED/CANCELLED
                for item in booking.items.all():
                    item.ticket_type.quantity_available += item.quantity
                    item.ticket_type.save(update_fields=["quantity_available"])
                print(f"Stock restored for booking {booking.booking_id}")


            # Jika ada perubahan status, simpan
            if new_status:
                booking.status = new_status
                booking.updated_at = timezone.now()
                booking.save(update_fields=['status', 'updated_at'])
                print(f"Booking {booking.booking_id} status updated to {new_status}")

                # FIX 7: HAPUS DATA SESSION SETELAH STATUS FINAL
                if "payment_responses" in request.session:
                    if str(booking.booking_id) in request.session["payment_responses"]:
                        del request.session["payment_responses"][str(booking.booking_id)]
                        print(f"Cleared session data for booking {booking.booking_id}")


        # Kirim respons 200 OK ke Midtrans agar tidak dikirim ulang
        return JsonResponse({'message': f'Notification processed for {order_id}, status: {booking.status}'}, status=200)

    except Exception as e:
        print(f"Webhook Error: {e}") # Log errornya
        # Kirim 500 tapi Midtrans mungkin akan retry
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def check_booking_status(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id, user=request.user)
        return JsonResponse({"status": booking.status})
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found or access denied"}, status=404)