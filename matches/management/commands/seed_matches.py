# matches/management/commands/seed_matches.py

import json
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from matches.models import Team, Venue, Match, TicketPrice

class Command(BaseCommand):
    help = 'Seeds the database with match data from the normalized match_cache.json'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Seeding database from normalized cache...'))
        
        # URL untuk logo placeholder
        PLACEHOLDER_LOGO_URL = "https://www.fotmob.com/img/league_logos/default_crests/leagues_150x150/default.png"
        
        cache_file = settings.BASE_DIR / 'match_cache.json'
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Error: Cache file not found at {cache_file}. Please run the main page first to generate it."))
            return
        
        normalized_matches = data.get('response', [])

        for match_data in normalized_matches:
            # Data sekarang sudah flat, jadi kita akses langsung
            
            # 1. Buat atau ambil data Venue
            # Gunakan .get() untuk keamanan jika data tidak ada
            venue, _ = Venue.objects.get_or_create(
                name=match_data.get('venue', 'N/A'),
                defaults={'city': match_data.get('city')}
            )

            # 2. Buat atau ambil data Tim (Home & Away)
            home_team, _ = Team.objects.get_or_create(
                api_id=match_data.get('home_team_api_id'),
                defaults={
                    'name': match_data.get('home_team'),
                    'logo_url': match_data.get('home_logo') or PLACEHOLDER_LOGO_URL
                }
            )
            
            away_team, _ = Team.objects.get_or_create(
                api_id=match_data.get('away_team_api_id'),
                defaults={
                    'name': match_data.get('away_team'),
                    'logo_url': match_data.get('away_logo') or PLACEHOLDER_LOGO_URL
                }
            )

            # 3. Buat atau update data Match
            match_datetime = datetime.fromisoformat(match_data['date_str'].replace('Z', '+00:00'))
            
            match, created = Match.objects.update_or_create(
                api_id=match_data.get('id'),
                defaults={
                    'home_team': home_team,
                    'away_team': away_team,
                    'venue': venue,
                    'date': match_datetime,
                    'status_short': "FT" if match_data.get('home_goals') is not None else "NS", # Contoh status sederhana
                    'status_long': "Match Finished" if match_data.get('home_goals') is not None else "Not Started",
                    'home_goals': match_data.get('home_goals'),
                    'away_goals': match_data.get('away_goals'),
                }
            )

            # 4. Buat harga tiket default jika match baru dibuat
            if created:
                TicketPrice.objects.create(match=match, seat_category='VVIP', price=500000, quantity_available=50)
                TicketPrice.objects.create(match=match, seat_category='VIP', price=300000, quantity_available=200)
                TicketPrice.objects.create(match=match, seat_category='REGULAR', price=150000, quantity_available=1000)

        self.stdout.write(self.style.SUCCESS('Database seeding complete!'))