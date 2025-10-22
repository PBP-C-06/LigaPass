import json
import uuid
import base64 # Import base64
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from authentication.models import User
from matches.models import Match, Team, Venue, TicketPrice
from .models import Booking, BookingItem, Ticket

class BookingViewsTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        """Set up non-modified objects used by all test methods."""
        # 1. Buat User
        cls.user = User.objects.create_user(username='testuser', password='password123', email='test@example.com', role='user')
        cls.other_user = User.objects.create_user(username='otheruser', password='password123', email='other@example.com', role='user')

        # 2. Buat Team & Venue
        cls.team1 = Team.objects.create(name='Team A', league='liga_1')
        cls.team2 = Team.objects.create(name='Team B', league='liga_1')
        cls.venue = Venue.objects.create(name='Stadium X', city='City Y')

        # 3. Buat Match
        cls.match_time = timezone.now() + timezone.timedelta(days=7)
        cls.match = Match.objects.create(
            home_team=cls.team1,
            away_team=cls.team2,
            venue=cls.venue,
            date=cls.match_time
        )

        # 4. Buat TicketPrice
        cls.ticket_price_regular = TicketPrice.objects.create(
            match=cls.match,
            seat_category='REGULAR',
            price=Decimal('100000.00'),
            quantity_available=50
        )
        cls.ticket_price_vip = TicketPrice.objects.create(
            match=cls.match,
            seat_category='VIP',
            price=Decimal('250000.00'),
            quantity_available=20
        )

        # 5. URL yang sering dipakai
        cls.create_booking_url = reverse('bookings:create_booking', kwargs={'match_id': cls.match.id})

    def setUp(self):
        """Set up client for each test."""
        self.client = Client()
        # Login user utama untuk kebanyakan tes
        self.client.login(username='testuser', password='password123')

    def test_create_booking_get_view(self):
        """Test GET request returns correct template and context."""
        response = self.client.get(self.create_booking_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'create_booking.html')
        self.assertIn('match', response.context)
        self.assertIn('ticket_prices', response.context)
        self.assertEqual(response.context['match'], self.match)
        self.assertEqual(len(response.context['ticket_prices']), 2)

    def test_create_booking_post_success(self):
        """Test successful booking creation via POST."""
        post_data = {
            "types": {
                "REGULAR": 2,
                "VIP": 1
            },
            "method": "gopay"
        }
        initial_regular_qty = self.ticket_price_regular.quantity_available
        initial_vip_qty = self.ticket_price_vip.quantity_available

        response = self.client.post(
            self.create_booking_url,
            data=json.dumps(post_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 201)
        json_response = response.json()
        self.assertIn('booking_id', json_response)
        self.assertEqual(json_response['total_price'], float(2 * 100000 + 1 * 250000))

        # Cek database
        booking_id = uuid.UUID(json_response['booking_id'])
        booking = Booking.objects.get(booking_id=booking_id)
        self.assertEqual(booking.user, self.user)
        self.assertEqual(booking.total_price, Decimal('450000.00'))
        self.assertEqual(booking.status, 'PENDING')
        self.assertEqual(booking.items.count(), 2)

        # Cek pengurangan stok
        self.ticket_price_regular.refresh_from_db()
        self.ticket_price_vip.refresh_from_db()
        self.assertEqual(self.ticket_price_regular.quantity_available, initial_regular_qty - 2)
        self.assertEqual(self.ticket_price_vip.quantity_available, initial_vip_qty - 1)

        # Cek session
        self.assertEqual(self.client.session.get('selected_method'), 'gopay')

    def test_create_booking_post_no_stock(self):
        """Test POST when not enough tickets are available."""
        self.ticket_price_regular.quantity_available = 1
        self.ticket_price_regular.save()

        post_data = {"types": {"REGULAR": 2}, "method": "gopay"}
        response = self.client.post(
            self.create_booking_url, data=json.dumps(post_data), content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertIn('Not enough tickets', response.json()['error'])
        # Pastikan stok tidak berubah negatif
        self.ticket_price_regular.refresh_from_db()
        self.assertEqual(self.ticket_price_regular.quantity_available, 1)
        self.assertFalse(Booking.objects.filter(user=self.user).exists())

    def test_create_booking_post_invalid_data(self):
        """Test POST with missing data."""
        # No tickets selected
        response = self.client.post(
            self.create_booking_url, data=json.dumps({"types": {}, "method": "gopay"}), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('No tickets selected', response.json()['error'])

        # No method selected
        response = self.client.post(
            self.create_booking_url, data=json.dumps({"types": {"REGULAR": 1}}), content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Payment method not selected', response.json()['error'])

    def test_create_booking_post_not_logged_in(self):
        """Test POST request when user is not logged in."""
        self.client.logout()
        post_data = {"types": {"REGULAR": 1}, "method": "gopay"}
        response = self.client.post(
            self.create_booking_url, data=json.dumps(post_data), content_type='application/json'
        )
        # Should redirect to login page
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('authentication:login'), response.url)

    def _create_test_booking(self, user, total_price=Decimal('100000.00'), status='PENDING'):
        """Helper to create a booking for payment tests."""
        booking = Booking.objects.create(
            user=user,
            total_price=total_price,
            status=status
        )
        BookingItem.objects.create(
            booking=booking,
            ticket_type=self.ticket_price_regular,
            quantity=1
        )
        return booking

    def test_payment_get_view(self):
        """Test GET request for payment page."""
        booking = self._create_test_booking(self.user)
        payment_url = reverse('bookings:payment', kwargs={'booking_id': booking.booking_id})

        # Set session manually
        session = self.client.session
        session['selected_method'] = 'gopay'
        session.save()

        response = self.client.get(payment_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'payment.html')
        self.assertEqual(response.context['booking'], booking)
        self.assertEqual(response.context['selected_method'], 'gopay')
        # Check session still exists (using .get() in view)
        self.assertEqual(self.client.session.get('selected_method'), 'gopay')

    # Mocking requests.post for Midtrans charge API
    @patch('requests.post')
    def test_payment_post_new_qris_success(self, mock_post):
        """Test successful POST to initiate a new QRIS payment."""
        booking = self._create_test_booking(self.user)
        payment_url = reverse('bookings:payment', kwargs={'booking_id': booking.booking_id})
        post_data = {"method": "gopay"}

        # Configure the mock response from Midtrans
        mock_midtrans_response = MagicMock()
        mock_midtrans_response.status_code = 201
        mock_midtrans_response.json.return_value = {
            "status_code": "201",
            "transaction_status": "pending",
            "order_id": f"book-gop-{booking.booking_id.hex[:8]}", # Match generated ID
            "actions": [{"name": "generate-qr-code", "url": "http://example.com/qr.png"}]
            # Add other relevant fields if needed
        }
        mock_post.return_value = mock_midtrans_response

        response = self.client.post(payment_url, data=json.dumps(post_data), content_type='application/json')

        self.assertEqual(response.status_code, 201)
        json_response = response.json()
        self.assertEqual(json_response['transaction_status'], 'pending')
        self.assertIn('actions', json_response)

        # Verify requests.post was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://api.sandbox.midtrans.com/v2/charge')
        self.assertEqual(kwargs['json']['payment_type'], 'qris')
        self.assertEqual(kwargs['json']['qris']['acquirer'], 'gopay')
        self.assertIn('item_details', kwargs['json'])

        # Verify database update
        booking.refresh_from_db()
        self.assertIsNotNone(booking.midtrans_order_id)
        self.assertTrue(booking.midtrans_order_id.startswith('book-gop-'))
        self.assertEqual(booking.status, 'PENDING') # Should be updated from Midtrans response

        # Verify session update
        self.assertIn('payment_responses', self.client.session)
        self.assertIn(str(booking.booking_id), self.client.session['payment_responses'])
        self.assertEqual(self.client.session['payment_responses'][str(booking.booking_id)]['status_code'], '201')

    def test_payment_post_refresh_with_session(self):
        """Test POST when refreshing payment page and data exists in session."""
        booking = self._create_test_booking(self.user)
        booking.midtrans_order_id = "test-order-123" # Set existing order ID
        booking.save()
        payment_url = reverse('bookings:payment', kwargs={'booking_id': booking.booking_id})
        post_data = {"method": "gopay"} # Method doesn't really matter here

        # Store mock response in session
        mock_stored_response = {
            "status_code": "201", "transaction_status": "pending", "order_id": "test-order-123",
            "actions": [{"name": "generate-qr-code", "url": "http://example.com/qr_from_session.png"}]
        }
        session = self.client.session
        session['payment_responses'] = {str(booking.booking_id): mock_stored_response}
        session.save()

        response = self.client.post(payment_url, data=json.dumps(post_data), content_type='application/json')

        # Should return the stored response
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, mock_stored_response)

    @patch('requests.get')
    def test_payment_post_refresh_without_session_fallback(self, mock_get):
        """Test POST refresh fallback: checks status API when session is empty."""
        booking = self._create_test_booking(self.user)
        booking.midtrans_order_id = "test-order-fallback"
        booking.save()
        payment_url = reverse('bookings:payment', kwargs={'booking_id': booking.booking_id})
        post_data = {"method": "gopay"}

        # Ensure session is empty for this booking
        session = self.client.session
        if 'payment_responses' in session and str(booking.booking_id) in session['payment_responses']:
            del session['payment_responses'][str(booking.booking_id)]
            session.save()

        # Mock the status check response
        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "status_code": "200", "transaction_status": "pending", "order_id": "test-order-fallback",
            # Status API doesn't usually return actions, JS might show error here
        }
        mock_get.return_value = mock_status_response

        response = self.client.post(payment_url, data=json.dumps(post_data), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, mock_status_response.json.return_value)

        # Build the expected headers used in the view's fallback
        server_key = settings.MIDTRANS_SERVER_KEY
        auth_str = base64.b64encode(f"{server_key}:".encode()).decode()
        expected_headers = {
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Verify status check API was called with the correct URL and headers
        mock_get.assert_called_once_with(
            f"https://api.sandbox.midtrans.com/v2/{booking.midtrans_order_id}/status",
            headers=expected_headers # Use the correctly built headers
        )

    def test_payment_post_already_processed(self):
        """Test POST attempt on an already confirmed booking."""
        booking = self._create_test_booking(self.user, status='CONFIRMED')
        payment_url = reverse('bookings:payment', kwargs={'booking_id': booking.booking_id})
        post_data = {"method": "gopay"}

        response = self.client.post(payment_url, data=json.dumps(post_data), content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn("already processed or expired", response.json()['error'])

    @patch('requests.post')
    def test_cancel_booking_success(self, mock_cancel_post):
        """Test successful booking cancellation."""
        booking = self._create_test_booking(self.user)
        booking.midtrans_order_id = "order-to-cancel" # Give it an order ID
        booking.save()
        cancel_url = reverse('bookings:cancel_booking', kwargs={'booking_id': booking.booking_id})
        initial_qty = self.ticket_price_regular.quantity_available

        # Mock Midtrans cancel response (optional, depends if you care about its success)
        mock_cancel_response = MagicMock()
        mock_cancel_response.status_code = 200
        mock_cancel_post.return_value = mock_cancel_response

        # Store something in session to check if it gets cleared
        session = self.client.session
        session['payment_responses'] = {str(booking.booking_id): {"data": "test"}}
        session.save()


        # Assuming POST request for cancellation
        response = self.client.post(cancel_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("cancelled successfully", response.json()['message'])

        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CANCELLED')

        # Check stock restoration
        self.ticket_price_regular.refresh_from_db()
        self.assertEqual(self.ticket_price_regular.quantity_available, initial_qty + 1)

        # Check Midtrans API call (optional)
        mock_cancel_post.assert_called_once()

        # Check session cleared
        self.assertNotIn(str(booking.booking_id), self.client.session.get('payment_responses', {}))

    def test_cancel_booking_already_confirmed(self):
        """Test cancelling an already confirmed booking."""
        booking = self._create_test_booking(self.user, status='CONFIRMED')
        cancel_url = reverse('bookings:cancel_booking', kwargs={'booking_id': booking.booking_id})
        initial_qty = self.ticket_price_regular.quantity_available

        response = self.client.post(cancel_url)

        self.assertEqual(response.status_code, 400)
        self.assertIn("cannot be cancelled", response.json()['message'])
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.ticket_price_regular.refresh_from_db()
        self.assertEqual(self.ticket_price_regular.quantity_available, initial_qty)

    def test_cancel_booking_not_owner(self):
        """Test cancelling booking belonging to another user."""
        booking = self._create_test_booking(self.other_user)
        cancel_url = reverse('bookings:cancel_booking', kwargs={'booking_id': booking.booking_id})

        response = self.client.post(cancel_url)

        self.assertEqual(response.status_code, 404)

    def test_midtrans_notification_settlement(self):
        """Test successful settlement notification."""
        booking = self._create_test_booking(self.user)
        booking.midtrans_order_id = "settlement-order-123"
        booking.save()
        notification_url = reverse('bookings:midtrans_notification')

        payload = {
            "order_id": booking.midtrans_order_id,
            "transaction_status": "settlement",
            "fraud_status": "accept",
            "status_code": "200",
        }

        response = self.client.post(notification_url, data=json.dumps(payload), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertTrue(Ticket.objects.filter(booking=booking).exists())
        self.assertEqual(Ticket.objects.filter(booking=booking).count(), 1)

    def test_midtrans_notification_expire(self):
        """Test expire notification restores stock."""
        booking = self._create_test_booking(self.user)
        booking.midtrans_order_id = "expire-order-123"
        booking.save()
        notification_url = reverse('bookings:midtrans_notification')
        initial_qty = self.ticket_price_regular.quantity_available

        payload = {
            "order_id": booking.midtrans_order_id,
            "transaction_status": "expire",
            "fraud_status": "accept",
            "status_code": "200",
        }

        response = self.client.post(notification_url, data=json.dumps(payload), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'EXPIRED')
        self.ticket_price_regular.refresh_from_db()
        self.assertEqual(self.ticket_price_regular.quantity_available, initial_qty + 1)
        self.assertFalse(Ticket.objects.filter(booking=booking).exists())

    def test_midtrans_notification_unknown_order(self):
        """Test notification for an order ID not in the database."""
        notification_url = reverse('bookings:midtrans_notification')
        payload = {"order_id": "unknown-order-id", "transaction_status": "settlement"}

        response = self.client.post(notification_url, data=json.dumps(payload), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn("Booking not found", response.json()['message'])

    def test_midtrans_notification_wrong_method(self):
        """Test GET request to notification URL."""
        notification_url = reverse('bookings:midtrans_notification')
        response = self.client.get(notification_url)
        self.assertEqual(response.status_code, 405)

    def test_check_booking_status_success(self):
        """Test checking status of own booking."""
        booking = self._create_test_booking(self.user)
        check_url = reverse('bookings:check_booking_status', kwargs={'booking_id': booking.booking_id})

        response = self.client.get(check_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "PENDING"})

        # Update status and check again
        booking.status = 'CONFIRMED'
        booking.save()
        response = self.client.get(check_url)
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "CONFIRMED"})

    def test_check_booking_status_not_owner(self):
        """Test checking status of another user's booking."""
        booking = self._create_test_booking(self.other_user)
        check_url = reverse('bookings:check_booking_status', kwargs={'booking_id': booking.booking_id})

        response = self.client.get(check_url)

        self.assertEqual(response.status_code, 404)
        self.assertIn("Booking not found", response.json()['error'])

    def test_check_booking_status_not_found(self):
        """Test checking status for non-existent booking ID."""
        invalid_uuid = uuid.uuid4()
        check_url = reverse('bookings:check_booking_status', kwargs={'booking_id': invalid_uuid})

        response = self.client.get(check_url)

        self.assertEqual(response.status_code, 404)