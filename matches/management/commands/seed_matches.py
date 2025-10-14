# matches/management/commands/seed_matches.py

import json
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from matches.models import Team, Venue, Match, TicketPrice

class Command(BaseCommand):
    help = 'Seeds the database with match data from match_cache.json'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Seeding database from cache...'))
        
        cache_file = settings.BASE_DIR / 'match_cache.json'
        try:
            with open(cache_file, 'r') as f:
                # PERBAIKAN ADA DI SINI
                data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"Error: Cache file not found at {cache_file}"))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f"Error: Could not decode JSON from {cache_file}"))
            return

        api_matches = data.get('response', [])

        for match_data in api_matches:
            # (Sisa dari kode ini sama dan sudah benar)
            venue_info = match_data['fixture']['venue']
            venue, _ = Venue.objects.get_or_create(
                api_id=venue_info.get('id'), # Gunakan .get() untuk keamanan
                defaults={
                    'name': venue_info.get('name', 'N/A'),
                    'city': venue_info.get('city')
                }
            )

            home_team_info = match_data['teams']['home']
            away_team_info = match_data['teams']['away']
            
            home_team, _ = Team.objects.get_or_create(
                api_id=home_team_info.get('id'),
                defaults={
                    'name': home_team_info.get('name'),
                    'logo_url': home_team_info.get('logo')
                }
            )
            
            away_team, _ = Team.objects.get_or_create(
                api_id=away_team_info.get('id'),
                defaults={
                    'name': away_team_info.get('name'),
                    'logo_url': away_team_info.get('logo')
                }
            )

            fixture_info = match_data['fixture']
            match_datetime = datetime.fromisoformat(fixture_info['date'].replace('Z', '+00:00'))
            
            match, created = Match.objects.update_or_create(
                api_id=fixture_info.get('id'),
                defaults={
                    'home_team': home_team,
                    'away_team': away_team,
                    'venue': venue,
                    'date': match_datetime,
                    'status_short': fixture_info['status']['short'],
                    'status_long': fixture_info['status']['long'],
                    'home_goals': match_data['goals']['home'],
                    'away_goals': match_data['goals']['away'],
                }
            )

            if created:
                TicketPrice.objects.create(match=match, seat_category='VVIP', price=500000, quantity_available=50)
                TicketPrice.objects.create(match=match, seat_category='VIP', price=300000, quantity_available=200)
                TicketPrice.objects.create(match=match, seat_category='REGULAR', price=150000, quantity_available=1000)

        self.stdout.write(self.style.SUCCESS('Database seeding complete!'))
