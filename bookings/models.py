import uuid
from django.db import models
from django.conf import settings
from matches.models import TicketPrice

class Booking(models.Model):
    booking_status = [
        ('PENDING', 'Menunggu Pembayaran'),
        ('CONFIRMED', 'Terkonfirmasi'),
        ('EXPIRED', 'Kadaluarsa')
    ]
    
    booking_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    midtrans_order_id = models.CharField(max_length=100, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=10, choices=booking_status, default='PENDING')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking {self.booking_id} by {self.user.username}"

class BookingItem(models.Model):
    ticket_type = [
        ('Regular', 'Regular'),
        ('VIP', 'VIP'),
        ('VVIP', 'VVIP'),
    ]
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='items')
    ticket_type = models.ForeignKey(TicketPrice, choices=ticket_type, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.ticket_type.seat_category} for {self.booking}"

class Ticket(models.Model):
    ticket_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='tickets')
    ticket_type = models.ForeignKey(TicketPrice, on_delete=models.PROTECT)
    is_used = models.BooleanField(default=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.ticket_id} ({self.ticket_type.seat_category} for match {self.ticket_type.match.id}) for Booking {self.booking.booking_id}"