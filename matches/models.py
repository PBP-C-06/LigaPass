import uuid
from django.db import models
from django.templatetags.static import static

class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    LIGA_CHOICES = [
        ('liga_1', 'Liga 1'),
        ('liga_2', 'Liga 2'),
        ('n/a', 'Tidak Diketahui'),
    ]

    api_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    league = models.CharField(max_length=10, choices=LIGA_CHOICES, default='n/a')

    @property
    def static_logo_filename(self):
        if not self.name:
            return "default.png"
        return self.name.lower().replace(' ', '_') + '.png'

    @property
    def display_logo_url(self):
        if self.logo_url:
            return self.logo_url
        file_name = self.static_logo_filename
        path = f"matches/images/team_logos/{self.league}/{file_name}"
        return static(path)

    def __str__(self):
        return self.name

class Venue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    api_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.name}, {self.city}"

class Match(models.Model):
    # Sudah menggunakan UUID sejak awal
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    api_id = models.IntegerField(unique=True, null=True, blank=True)
    
    # ForeignKey ke Team sekarang otomatis menggunakan UUID
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    
    # ForeignKey ke Venue sekarang otomatis menggunakan UUID
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField()
    
    status_short = models.CharField(max_length=10, default="NS")
    status_long = models.CharField(max_length=50, default="Not Started")
    
    home_goals = models.IntegerField(null=True, blank=True)
    away_goals = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} on {self.date.strftime('%Y-%m-%d')}"
    
class TicketPrice(models.Model):
    SEAT_CATEGORIES = [
        ('VVIP', 'VVIP'),
        ('VIP', 'VIP'),
        ('REGULAR', 'Regular'),
    ]

    # ForeignKey ke Match menggunakan UUID
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='ticket_prices')
    
    seat_category = models.CharField(max_length=10, choices=SEAT_CATEGORIES)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    quantity_available = models.PositiveIntegerField(default=0, help_text="Jumlah tiket yang tersedia untuk kategori ini")

    class Meta:
        unique_together = ('match', 'seat_category')

    def __str__(self):
        return f"{self.get_seat_category_display()} - {self.match} - Rp {self.price}"