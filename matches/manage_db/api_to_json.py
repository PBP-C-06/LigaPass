import os
import django
import sys
import json
from pathlib import Path

# Dapatkan path absolut ke direktori script saat ini (matches/manage_db/)
CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_SCRIPT_DIR.parent.parent 

# Tambahkan Project Root ke sys.path agar modul 'LigaPass' dapat ditemukan
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Mengatur environment Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LigaPass.settings')

# Inisialisasi Django
try:
    # django.setup() sekarang bisa menemukan 'LigaPass.settings'
    django.setup() 
except Exception as e:
    print("ERROR: Gagal menginisialisasi Django. Pastikan Anda berada di virtual environment yang benar.")
    print(e)
    sys.exit(1)

# Import setelah django.setup()
from matches.services import _fetch_freeapi_matches, _normalize_match_data, _save_to_json 

print("--- Memulai API CALL dan menyimpan ke JSON ---")

raw_data = _fetch_freeapi_matches()
if not raw_data:
    print("Operasi dibatalkan: Gagal mengambil data dari API.")
    sys.exit(1)

all_matches = []
processed_ids = set()
for match in raw_data:
    normalized = _normalize_match_data(match)
    if normalized and normalized['id'] not in processed_ids:
        all_matches.append(normalized)
        processed_ids.add(normalized['id'])

if all_matches:
    _save_to_json(all_matches)
    print("SUKSES: Data API baru telah disimpan ke matches_backup.json.")
else:
    print("GAGAL: Data yang diambil dari API tidak valid atau kosong.")