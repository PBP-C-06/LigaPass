from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from bookings.models import *
from matches.models import *
import requests, json, base64, uuid
from django.conf import settings
from django.utils import timezone
from django.urls import reverse

@login_required
def flutter_get_ticket_prices(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    ticket_prices = TicketPrice.objects.filter(match=match).order_by('price')
    
    tickets = []
    for tp in ticket_prices:
        tickets.append({
            'id': tp.id,
            'match_id': str(tp.match.id),
            'seat_category': tp.seat_category,
            'price': float(tp.price),
            'quantity_available': tp.quantity_available,
        })
    
    return JsonResponse({
        'status': True,
        'match': {
            'id': str(match.id),
            'title': f"{match.home_team.name} vs {match.away_team.name}",
        },
        'tickets': tickets,
    })
    
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

@csrf_exempt
@login_required
def flutter_create_booking(request, match_id):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid method"}, status=405)

    body = json.loads(request.body)
    ticket_types = body.get("ticket_types", {})
    method = body.get("payment_method")

    if not ticket_types:
        return JsonResponse({"status": False, "message": "Empty ticket selection"})

    match = get_object_or_404(Match, id=match_id)

    total = 0
    items = []

    # validate & reserve
    for seat_cat, qty in ticket_types.items():
        tp = TicketPrice.objects.filter(match=match, seat_category=seat_cat).first()
        if not tp:
            return JsonResponse({"status": False, "message": f"{seat_cat} not found"})

        qty = int(qty)
        if tp.quantity_available < qty:
            return JsonResponse({"status": False, "message": f"Insufficient {seat_cat}"})

        # Reserve stock
        tp.quantity_available -= qty
        tp.save()

        total += float(tp.price) * qty
        items.append((tp, qty))

    # create booking
    booking = Booking.objects.create(
        user=request.user,
        total_price=total,
        status="PENDING",
    )

    for tp, qty in items:
        BookingItem.objects.create(
            booking=booking,
            ticket_type=tp,
            quantity=qty,
        )

    # Return to Flutter
    return JsonResponse({
        "status": True,
        "booking_id": str(booking.booking_id),
        "total_price": total,
        "payment_method": method,
    })

    
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
                return JsonResponse({
                    "error": "Sesi pembayaran Anda telah berakhir. Silakan buat booking baru."
                }, status=410)

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

@csrf_exempt
@login_required
def flutter_payment(request, booking_id):
    if request.method != "POST":
        return JsonResponse({"status": False, "message": "Invalid method"}, 405)

    booking = get_object_or_404(Booking, booking_id=booking_id, user=request.user)
    body = json.loads(request.body)
    method = body.get("method")
    token_id = body.get("token_id")

    server_key = settings.MIDTRANS_SERVER_KEY
    auth = base64.b64encode(f"{server_key}:".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Prevent duplicate payment
    if booking.midtrans_order_id:
        return JsonResponse({"status": False, "message": "Order already processed"})

    order_id = f"mb-{uuid.uuid4().hex[:8]}"

    payload = {
        "transaction_details": {
            "order_id": order_id,
            "gross_amount": int(booking.total_price),
        },
        "customer_details": {
            "first_name": booking.user.username,
            "email": booking.user.email,
        },
        "item_details": [
            {
                "id": item.id,
                "price": float(item.ticket_type.price),
                "quantity": item.quantity,
                "name": f"Ticket {item.ticket_type.seat_category}"
            }
            for item in booking.items.all()
        ],
    }

    # Payment type
    if method == "gopay":
        payload["payment_type"] = "qris"
        payload["qris"] = {"acquirer": "gopay"}

    elif method.startswith("bank_"):
        bank = method.split("_")[1]
        payload["payment_type"] = "bank_transfer"
        payload["bank_transfer"] = {"bank": bank}

    elif method == "credit_card":
        if not token_id:
            return JsonResponse({"status": False, "message": "Missing card token"})
        payload["payment_type"] = "credit_card"
        payload["credit_card"] = {
            "token_id": token_id,
            "authentication": True,
        }

    else:
        return JsonResponse({"status": False, "message": "Invalid method"})

    # Midtrans call
    try:
        res = requests.post(
            "https://api.sandbox.midtrans.com/v2/charge",
            headers=headers,
            json=payload,
        )
        mid_data = res.json()
    except:
        return JsonResponse({"status": False, "message": "Midtrans request failed"})

    # Save booking
    booking.midtrans_order_id = order_id
    booking.midtrans_actions = mid_data.get("actions", [])
    booking.status = mid_data.get("transaction_status", "PENDING").upper()
    booking.save()

    return JsonResponse({
        "status": True,
        "payment_data": mid_data,
    })

    
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

@csrf_exempt
@login_required
def flutter_cancel_booking(request, booking_id):
    booking = Booking.objects.filter(booking_id=booking_id, user=request.user).first()

    if not booking:
        return JsonResponse({"status": False, "message": "Not found"})

    if booking.status != "PENDING":
        return JsonResponse({"status": False, "message": "Cannot cancel"})

    # restore stock
    for item in booking.items.all():
        item.ticket_type.quantity_available += item.quantity
        item.ticket_type.save()

    booking.status = "CANCELLED"
    booking.save()

    return JsonResponse({"status": True, "message": "Booking cancelled"})

@login_required
def check_booking_status(request, booking_id):
    try:
        booking = Booking.objects.get(booking_id=booking_id, user=request.user)
        return JsonResponse({"status": booking.status})
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found"}, status=404)

@login_required
def flutter_check_status(request, booking_id):
    booking = Booking.objects.filter(booking_id=booking_id, user=request.user).first()
    if not booking:
        return JsonResponse({"status": False, "message": "Not found"})

    return JsonResponse({
        "status": True,
        "payment_status": booking.status,
    })


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

@csrf_exempt
@login_required
def flutter_get_user_tickets(request):
    if request.method == 'GET':
        tickets = Ticket.objects.filter(
            booking__user=request.user,
            booking__status='CONFIRMED'
        ).select_related(
            'booking', 'ticket_type', 
            'ticket_type__match', 
            'ticket_type__match__home_team',
            'ticket_type__match__away_team',
            'ticket_type__match__venue'
        ).order_by('-generated_at')
        
        tickets_data = []
        for ticket in tickets:
            match = ticket.ticket_type.match
            
            is_match_finished = match.date < timezone.now()
            effective_used = ticket.is_used or is_match_finished
            
            # Use same method as matches app - build absolute URI with reverse
            home_logo_url = None
            away_logo_url = None
            if match.home_team:
                home_logo_url = request.build_absolute_uri(
                    reverse('matches:flutter_team_logo_proxy', args=[match.home_team.id])
                )
            if match.away_team:
                away_logo_url = request.build_absolute_uri(
                    reverse('matches:flutter_team_logo_proxy', args=[match.away_team.id])
                )
            
            tickets_data.append({
                'id': str(ticket.ticket_id),
                'booking_id': str(ticket.booking.booking_id),
                'seat_category': ticket.ticket_type.seat_category,
                'match_title': f"{match.home_team.name} vs {match.away_team.name}",
                'home_team': match.home_team.name,
                'away_team': match.away_team.name,
                'home_team_logo': home_logo_url,
                'away_team_logo': away_logo_url,
                'match_date': match.date.isoformat() if match.date else None,
                'venue': match.venue.name if match.venue else None,
                'city': match.venue.city if match.venue else None,
                'is_used': effective_used,
                'is_match_finished': is_match_finished,
                'generated_at': ticket.generated_at.isoformat(),
                'qr_code': '',
            })
        
        return JsonResponse({
            'status': True,
            'tickets': tickets_data
        })
    
    return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)

@csrf_exempt
@login_required
def flutter_get_booking_tickets(request, booking_id):
    if request.method == 'GET':
        try:
            booking = Booking.objects.get(booking_id=booking_id, user=request.user)
            tickets = booking.tickets.select_related(
                'ticket_type',
                'ticket_type__match',
                'ticket_type__match__home_team',
                'ticket_type__match__away_team',
                'ticket_type__match__venue',
            ).all()
            
            tickets_data = []
            for ticket in tickets:
                match = ticket.ticket_type.match
                
                # Use same method as matches app
                home_logo_url = None
                away_logo_url = None
                if match.home_team:
                    home_logo_url = request.build_absolute_uri(
                        reverse('matches:flutter_team_logo_proxy', args=[match.home_team.id])
                    )
                if match.away_team:
                    away_logo_url = request.build_absolute_uri(
                        reverse('matches:flutter_team_logo_proxy', args=[match.away_team.id])
                    )
                
                tickets_data.append({
                    'id': str(ticket.ticket_id),
                    'booking_id': str(booking.booking_id),
                    'seat_category': ticket.ticket_type.seat_category,
                    'match_title': f"{match.home_team.name} vs {match.away_team.name}",
                    'home_team': match.home_team.name,
                    'away_team': match.away_team.name,
                    'home_team_logo': home_logo_url,
                    'away_team_logo': away_logo_url,
                    'match_date': match.date.isoformat() if match.date else None,
                    'venue': match.venue.name if match.venue else None,
                    'city': match.venue.city if match.venue else None,
                    'is_used': ticket.is_used,
                    'generated_at': ticket.generated_at.isoformat(),
                    'qr_code': '',
                })
            
            return JsonResponse({
                'status': True,
                'booking_id': str(booking.booking_id),
                'tickets': tickets_data
            })
        except Booking.DoesNotExist:
            return JsonResponse({'status': False, 'message': 'Booking not found'}, status=404)
    
    return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)

@csrf_exempt
@login_required
def flutter_sync_status(request, booking_id):
    """
    Sync payment status from Midtrans API and update Django database.
    Uses direct HTTP request instead of midtransclient.
    """
    if request.method == 'POST':
        try:
            booking = Booking.objects.get(booking_id=booking_id, user=request.user)
            
            # If already confirmed, return immediately
            if booking.status == 'CONFIRMED':
                return JsonResponse({
                    'status': True,
                    'payment_status': 'CONFIRMED',
                    'message': 'Payment already confirmed'
                })
            
            # Check if we have midtrans_order_id
            if not booking.midtrans_order_id:
                return JsonResponse({
                    'status': False,
                    'payment_status': booking.status,
                    'message': 'No Midtrans order ID found for this booking'
                })
            
            # Use the actual order_id stored in booking
            order_id = booking.midtrans_order_id
            
            # Midtrans API endpoint for checking transaction status
            midtrans_url = f"https://api.sandbox.midtrans.com/v2/{order_id}/status"
            
            # Create authorization header
            server_key = settings.MIDTRANS_SERVER_KEY
            auth_string = base64.b64encode(f"{server_key}:".encode()).decode()
            
            headers = {
                'Authorization': f'Basic {auth_string}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Query Midtrans API
            response = requests.get(midtrans_url, headers=headers)
            
            print(f"Midtrans status check for {order_id}: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                transaction_status = data.get('transaction_status', '')
                fraud_status = data.get('fraud_status', 'accept')
                
                # Map Midtrans status to booking status
                if transaction_status == 'capture':
                    if fraud_status == 'accept':
                        if booking.status != 'CONFIRMED':
                            booking.status = 'CONFIRMED'
                            booking.save()
                            # Generate tickets
                            for item in booking.items.all():
                                for _ in range(item.quantity):
                                    Ticket.objects.create(booking=booking, ticket_type=item.ticket_type)
                                    
                elif transaction_status == 'settlement':
                    if booking.status != 'CONFIRMED':
                        booking.status = 'CONFIRMED'
                        booking.save()
                        # Generate tickets
                        for item in booking.items.all():
                            for _ in range(item.quantity):
                                Ticket.objects.create(booking=booking, ticket_type=item.ticket_type)
                                
                elif transaction_status in ['cancel', 'deny', 'expire']:
                    if booking.status not in ['CANCELLED', 'EXPIRED']:
                        booking.status = 'CANCELLED' if transaction_status != 'expire' else 'EXPIRED'
                        booking.save()
                        # Restore stock
                        for item in booking.items.all():
                            item.ticket_type.quantity_available += item.quantity
                            item.ticket_type.save()
                
                return JsonResponse({
                    'status': True,
                    'payment_status': booking.status,
                    'midtrans_status': transaction_status,
                    'message': f'Status synced: {transaction_status}'
                })
            
            elif response.status_code == 404:
                return JsonResponse({
                    'status': False,
                    'payment_status': booking.status,
                    'message': f'Transaction {order_id} not found in Midtrans'
                })
            else:
                return JsonResponse({
                    'status': False,
                    'payment_status': booking.status,
                    'message': f'Midtrans API error: {response.status_code} - {response.text}'
                })
                
        except Booking.DoesNotExist:
            return JsonResponse({
                'status': False,
                'message': 'Booking not found'
            }, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'status': False,
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': False, 'message': 'Method not allowed'}, status=405)