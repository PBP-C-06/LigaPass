import os
import django
import sys
from django.core.cache import cache
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
from matches.services import _load_from_json, CACHE_KEY_SYNC, CACHE_TIMEOUT

print("--- Memulai JSON Dump ke Django Cache ---")

data_from_json = _load_from_json()

if data_from_json:
    cache.set(CACHE_KEY_SYNC, data_from_json, timeout=CACHE_TIMEOUT)
    print(f"SUKSES: {len(data_from_json)} entri dari JSON telah dimasukkan ke Django Cache.")
else:
    print("GAGAL: Tidak ada data valid yang dimuat dari JSON untuk di-cache.")