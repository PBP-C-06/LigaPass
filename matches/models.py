# matches/models.py

from django.db import models

class Team(models.Model):
    # Menyimpan ID unik dari API untuk menghindari duplikasi saat update
    api_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)
    logo_url = models.URLField(max_length=255)

    def __str__(self):
        return self.name

class Venue(models.Model):
    # Menyimpan ID unik dari API
    api_id = models.IntegerField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.name}, {self.city}"

class Match(models.Model):
    # Menyimpan ID unik dari API
    api_id = models.IntegerField(unique=True)
    
    # Dua ForeignKey ke model yang sama (Team)
    # related_name diperlukan agar Django bisa membedakannya
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField()
    
    status_short = models.CharField(max_length=10)
    status_long = models.CharField(max_length=50)
    
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

    # Menghubungkan harga ini ke pertandingan tertentu
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='ticket_prices')
    
    seat_category = models.CharField(max_length=10, choices=SEAT_CATEGORIES)
    
    # Gunakan DecimalField untuk uang agar tidak ada error pembulatan
    price = models.DecimalField(max_digits=10, decimal_places=2) # Contoh: 99999999.99
    
    # (Opsional tapi sangat direkomendasikan) Tambahkan kuota tiket
    quantity_available = models.PositiveIntegerField(default=0, help_text="Jumlah tiket yang tersedia untuk kategori ini")

    class Meta:
        # Memastikan tidak ada duplikasi kategori tiket untuk pertandingan yang sama
        unique_together = ('match', 'seat_category')

    def __str__(self):
        return f"{self.get_seat_category_display()} - {self.match} - Rp {self.price}"
