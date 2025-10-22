# pbp-c-06/ligapass/LigaPass-295f803d1f6f3d40afe67918fcc353e296533dc5/matches/admin.py

from django.contrib import admin
from .models import Team, Venue, Match, TicketPrice

# Tampilan inline untuk mengedit harga tiket langsung di halaman Match
class TicketPriceInline(admin.TabularInline):
    model = TicketPrice
    extra = 1 # Tampilkan 1 form kosong tambahan

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'date', 'venue', 'status_short')
    list_filter = ('date', 'status_short', 'venue')
    search_fields = ('home_team__name', 'away_team__name', 'venue__name')
    inlines = [TicketPriceInline]

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'api_id')
    search_fields = ('name',)

# Daftarkan model lainnya
admin.site.register(Venue)