# matches/models.py

import uuid
from django.db import models
from django.templatetags.static import static

class Team(models.Model):
    LIGA_CHOICES = [
        ('liga_1', 'Liga 1'),
        ('liga_2', 'Liga 2'),
        ('n/a', 'Tidak Diketahui'), # Untuk default/tim yang belum jelas
    ]

    # Primary key: name
    api_id = models.IntegerField(null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    league = models.CharField(max_length=10, choices=LIGA_CHOICES, default='n/a')

    @property
    def static_logo_filename(self):
        """Menghasilkan nama file yang diharapkan (misal: 'bali_united.png')."""
        if not self.name:
            return "default.png"
        return self.name.lower().replace(' ', '_') + '.png'

    @property
    def display_logo_url(self):
        """Memilih antara Logo API/DB (P1) dan Static Fallback Liga-spesifik (P2)."""
        
        # Prioritas 1: Logo API/URL (jika logo_url di DB tidak None/kosong)
        if self.logo_url:
            return self.logo_url
        
        # Prioritas 2: Logo Statis (Menggunakan atribut 'liga' untuk menentukan sub-folder)
        file_name = self.static_logo_filename
        
        path = f"matches/images/team_logos/{self.league}/{file_name}"
        
        return static(path)

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
    # Menggunakan UUID sebagai primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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
    
    # Tambahkan kuota tiket
    quantity_available = models.PositiveIntegerField(default=0, help_text="Jumlah tiket yang tersedia untuk kategori ini")

    class Meta:
        # Memastikan tidak ada duplikasi kategori tiket untuk pertandingan yang sama
        unique_together = ('match', 'seat_category')

    def __str__(self):
        return f"{self.get_seat_category_display()} - {self.match} - Rp {self.price}"