import uuid
from django.db import models
from django.conf import settings
from matches.models import Match 

class Booking(models.Model):
    booking_status = [
        ('PENDING', 'Menunggu Pembayaran'),
        ('CONFIRMED', 'Terkonfirmasi'),
        ('CANCELLED', 'Dibatalkan'),
        ('EXPIRED', 'Kadaluarsa')
    ]
    
    booking_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    match = models.ForeignKey(Match, on_delete=models.PROTECT, related_name='bookings')
    status = models.CharField(max_length=10, choices=booking_status, default='PENDING')
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking {self.booking_id} by {self.user.username} for match {self.match.id}"

class Ticket(models.Model):
    TICKET_TYPE_CHOICES = [
        ('VVIP', 'VVIP'),
        ('VIP', 'VIP'),
        ('REGULER', 'Reguler'),
    ]

    ticket_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='tickets')
    ticket_type = models.CharField(max_length=10, choices=TICKET_TYPE_CHOICES)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='tickets')
    is_used = models.BooleanField(default=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.ticket_id} ({self.ticket_type})"