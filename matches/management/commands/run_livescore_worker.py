import time
from datetime import timedelta
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from matches.models import Match

class Command(BaseCommand):
    help = 'Menjalankan worker untuk mengambil live score secara periodik.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Memulai Live Score Worker...")
        channel_layer = get_channel_layer()

        while True:
            try:
                now = timezone.now()
                safe_past_time = now - timedelta(hours=4) 
                
                ongoing_matches_qs = Match.objects.filter(
                    date__lte=now,
                    date__gte=safe_past_time
                ).exclude(status_short='FT')
                
                if not ongoing_matches_qs.exists():
                    self.stdout.write("Tidak ada pertandingan berlangsung. Worker tidur...")
                    time.sleep(180)
                    continue
                
                self.stdout.write("Mengambil data live dari Free API...")
                
                url = "https://free-api-live-football-data.p.rapidapi.com/football-current-live"
                headers = {
                    "x-rapidapi-host": "free-api-live-football-data.p.rapidapi.com",
                    "x-rapidapi-key": settings.RAPID_API_KEY
                }
                
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    api_data = response.json().get('response', {}).get('live', [])
                except Exception as e:
                    self.stderr.write(f"Gagal mengambil data dari Free API: {e}")
                    time.sleep(60)
                    continue

                if not api_data:
                    self.stdout.write("Tidak ada pertandingan live yang ditemukan di Free API. Worker tidur...")
                    time.sleep(180)
                    continue

                api_id_map = {match['id']: match for match in api_data}
                updated_count = 0

                for match in ongoing_matches_qs:
                    match_api_id = match.api_id
                    
                    if match_api_id in api_id_map:
                        live_match = api_id_map[match_api_id]
                        
                        status_str = live_match['status'].get('short', '')
                        home_goals = live_match['home']['score']
                        away_goals = live_match['away']['score']

                        elapsed_time_str = live_match['status']['liveTime'].get('long', '0:00') if live_match['status'].get('liveTime') else '0:00'

                        live_data = {
                            'home_goals': home_goals,
                            'away_goals': away_goals,
                            'status_short': status_str,
                            'elapsed': elapsed_time_str,
                            'status_long': live_match['status'].get('long', 'Ongoing')
                        }

                        match.home_goals = home_goals
                        match.away_goals = away_goals
                        match.status_short = live_data['status_short']
                        match.status_long = live_match['status']['long']
                        match.save()
                        updated_count += 1
                                        
                        async_to_sync(channel_layer.group_send)(
                            f'match_{match_api_id}',
                            {
                                'type': 'match_update',
                                'message': live_data
                            }
                        )
                        self.stdout.write(f"Update dikirim untuk match {match_api_id}")

                self.stdout.write(f"Total {updated_count} pertandingan diperbarui dan dikirim. Worker tidur...")
                
                time.sleep(180)

            except Exception as e:
                self.stderr.write(f"Terjadi error pada worker: {e}")
                time.sleep(60)