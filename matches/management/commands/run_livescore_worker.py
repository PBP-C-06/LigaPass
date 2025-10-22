import asyncio
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
                # Menggunakan margin aman 4 jam untuk mencakup pertandingan yang:
                # 1. Sedang berlangsung (Ongoing) sesuai definisi 2.5 jam di views.
                # 2. Baru saja selesai tetapi API belum mengirim status FT atau status FT belum terkirim ke DB.
                safe_past_time = now - timedelta(hours=4) 
                
                ongoing_matches = Match.objects.filter(
                    date__lte=now,                   # Match harus sudah dimulai
                    date__gte=safe_past_time         # Dimulai dalam 4 jam terakhir
                ).exclude(status_short='FT').order_by('date')
                
                if ongoing_matches.exists():
                    self.stdout.write(f"Menemukan {ongoing_matches.count()} pertandingan berlangsung. Mengambil data live...")
                    
                    for match in ongoing_matches:
                        # Panggil API untuk mendapatkan data live
                        url = f"https://v3.football.api-sports.io/fixtures?id={match.api_id}"
                        headers = {
                            'x-rapidapi-key': settings.API_FOOTBALL_KEY,
                            'x-rapidapi-host': 'v3.football.api-sports.io'
                        }
                        
                        try:
                            response = requests.get(url, headers=headers, timeout=10)
                            response.raise_for_status()
                            api_data = response.json()['response'][0]

                            # Data yang akan dikirim ke frontend
                            live_data = {
                                'home_goals': api_data['goals']['home'],
                                'away_goals': api_data['goals']['away'],
                                'status_short': api_data['fixture']['status']['short'],
                                'elapsed': api_data['fixture']['status']['elapsed'],
                            }

                            # Update database lokal (menggunakan data yang benar dari API, termasuk status FT)
                            match.home_goals = live_data['home_goals']
                            match.away_goals = live_data['away_goals']
                            match.status_short = live_data['status_short']
                            match.status_long = api_data['fixture']['status']['long']
                            match.save()

                            # Kirim update ke grup channel yang sesuai
                            async_to_sync(channel_layer.group_send)(
                                f'match_{match.api_id}',
                                {
                                    'type': 'match_update',
                                    'message': live_data
                                }
                            )
                            self.stdout.write(f"Update dikirim untuk match {match.api_id}")

                        except Exception as e:
                            self.stderr.write(f"Gagal mengambil atau memproses data untuk match {match.api_id}: {e}")

                else:
                    self.stdout.write("Tidak ada pertandingan berlangsung. Worker tidur...")
                
                # Worker akan tidur selama 3 menit sebelum cek lagi
                time.sleep(180)

            except Exception as e:
                self.stderr.write(f"Terjadi error pada worker: {e}")
                time.sleep(60) # Tunggu 1 menit sebelum mencoba lagi jika ada error besar