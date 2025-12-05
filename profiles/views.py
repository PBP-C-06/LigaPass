import hashlib
import json
from django.urls import reverse
from django.middleware.csrf import get_token
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from dotenv import get_key
from django.templatetags.static import static
from authentication.models import User
from authentication.views import flutter_logout, logout_user
from profiles.models import AdminJournalistProfile, Profile
from bookings.models import Booking, Ticket
# import base64
# import imghdr
from django.core.files.base import ContentFile

# Create profile untuk user yang baru registrasi
@login_required
def create_profile(request):
    if request.method == "GET":
        return render(request, "create_profile.html")
    elif request.method == "POST":
        user = request.user

        # Validasi supaya admin dan journalist tidak dapat membuat profile lagi 
        if user.role == "admin" or user.role == "journalist":
            return JsonResponse({"ok": False, "message": "Profil sudah terdaftar sebelumnya."}, status=400)
        
        # Validasi supaya profile tidak lebih dari satu
        if (hasattr(request.user, 'profile')):
            return JsonResponse({"ok": False, "message": "Profil sudah terdaftar sebelumnya."}, status=400)
        
        # Mengambil data dari form
        profile_picture = request.FILES.get("profile_picture")
        date_of_birth = request.POST.get("date_of_birth")
        phone_number = request.POST.get("phone")

        # Buat sesuai dengan input dari form user
        Profile.objects.create(
            user = request.user,
            profile_picture = profile_picture,
            date_of_birth = date_of_birth,
            status = 'active',
        )

        # Simpan phone number dan status complete profile
        request.user.phone = phone_number
        request.user.profile_completed = True
        request.user.save()

        return JsonResponse({"ok": True, "message": "Profil berhasil di daftarkan."}, status=201)

# Menampilkan JSON 
def show_json(request):
    profiles = Profile.objects.select_related('user').all()
    data = [
        {
            "id": str(p.user.id),
            "username": p.user.username,
            "email": p.user.email,
            "full_name": p.full_name,
            "phone": str(p.user.phone) if p.user.phone else None,
            "profile_picture": p.profile_picture.url if p.profile_picture else None,
            "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            "status": p.status if hasattr(p, "status") else None,  
        }
        for p in profiles
    ]
    return JsonResponse(data, safe=False)

# Menampilkan JSON by id
def show_json_by_id(request, id):
    try:
        user = User.objects.get(pk=id)

        # Cek apakah user sudah login atau belum
        if request.user.is_authenticated:
            user_role = request.user.role
        else:
            user_role = "anonymous"

        data = {"role": user_role}

        # Jika role adalah admin atau administrator maka data adalah username dan profile picture saja
        if user.role == 'admin' or user.role == 'journalist':
            profile = getattr(user, 'adminjournalistprofile', None)
            data.update ({
                "username": user.username,
                "profile_picture" : profile.profile_picture if profile and profile.profile_picture else None,
            })
            return JsonResponse(data)
        else: # Jika role bukan user / journalist (user) maka tampilkan data sebagai berikut
            profile = getattr(user, 'profile', None)
            data.update({
                "id": user.id,
                "full_name": profile.full_name,
                "username": user.username,
                "email": user.email,
                "phone": str(user.phone) if user.phone else None,
                "status": profile.status,
                "date_of_birth": profile.date_of_birth.strftime('%Y-%m-%d') if profile and profile.date_of_birth else None,
                "profile_picture": profile.profile_picture.url if profile and profile.profile_picture else None,
            })
            return JsonResponse(data)
    except User.DoesNotExist:
        return JsonResponse({'error':'User Not Found'}, status=404)

# Menampilkan JSON admin
def show_json_admin(request):
    try:
        # Ambil hardcode admin
        admin = User.objects.filter(role='admin').first()
        admin_profile = getattr(admin, 'adminjournalistprofile', None)

        data = {
            "username": "admin",
            "profile_picture": admin_profile.profile_picture if admin_profile else None,
            "total_news": admin_profile.news_count if admin_profile else 0,
            "total_views": admin_profile.total_news_views if admin_profile else 0
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
# Menampilkan JSON untuk journalist
def show_json_journalist(request):
    try:
        # Ambil hardcode journalist
        journalist = User.objects.filter(role='journalist').first()
        journalist_profile = getattr(journalist, 'adminjournalistprofile', None)

        data = {
            "username": "journalist",
            "profile_picture": journalist_profile.profile_picture if journalist_profile else None,
            "total_news": journalist_profile.news_count if journalist_profile else 0,
            "total_views": journalist_profile.total_news_views if journalist_profile else 0
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# JSON untuk search dan filter pada admin view
def admin_search_filter(request):
    search = request.GET.get("search", "")
    filter_type = request.GET.get("filter", "all")

    # Ambil semua profile
    profiles = Profile.objects.select_related("user").all()
    
    # Search by username
    if search:
        profiles = profiles.filter(user__username__icontains=search)

    # Filter by status 
    if filter_type != "all":
        profiles = profiles.filter(status=filter_type)

    data = [
        {   
            "id": str(p.user.id),
            "username": p.user.username,
            "email": p.user.email,
            "full_name": p.full_name,
            "phone": str(p.user.phone) if p.user.phone else None,
            "profile_picture": p.profile_picture.url if p.profile_picture else None,
            "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
            "status": p.status if hasattr(p, "status") else None,  
        }
        for p in profiles
    ]
    return JsonResponse(data, safe=False)

# Untuk menampilkan user_profile.html
def user_view(request, id):
    # Cari profile berdasarkan UUID
    try:
        profile = Profile.objects.get(user__id=id)
    except Profile.DoesNotExist:
        profile = None

    # Jika user sudah login maka ambil role dan id 
    if request.user.is_authenticated:
        role = request.user.role
        viewer_id = str(request.user.id)
    else: # Jika belum maka role adalah anonymous dan id none
        role = "anonymous"
        viewer_id = None
    
    context = {
        "id": str(profile.user.id) if profile else None, 
        "viewer_id": viewer_id or None,
        "viewer_role": role,
        "csrf_token": get_token(request) if request.user.is_authenticated else None,
    }
    return render(request, "user_profile.html", context)

# Untuk menampilkan admin_profile.html
def admin_view(request):
    return render(request, "admin_profile.html")

# Untuk menampilkan journalist_profile.html
def journalist_view(request):
    return render(request, "journalist_profile.html")

# Edit user profile untuk user
@login_required
def edit_profile_for_user(request, id):
    user = get_object_or_404(User, pk=id)

    # Sebagai prevention supaya user tidak bisa mengedit profile user yang lain
    if request.user != user:
        return JsonResponse({"ok": False, "message": "Kamu tidak memiliki izin untuk mengedit."}, status=403)
    
    if request.method == "GET":
        context = {
            "person":user,
            "profile": getattr(user, "profile", None)
        }
        return render(request, "user_edit.html", context)
    
    elif request.method == "POST":
        # Mengambil data dari form 
        profile_picture = request.FILES.get("profile_picture")
        date_of_birth = request.POST.get("date_of_birth")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        phone_number = request.POST.get("phone")

        # Simpan perubahan user
        user.first_name = first_name
        user.last_name = last_name
        user.username = username
        user.email = email
        user.phone = phone_number
        user.save()

        # Simpan perubahan profile
        profile = getattr(user, "profile", None)
        if (profile_picture):
            profile.profile_picture = profile_picture
        profile.date_of_birth = date_of_birth
        profile.save()

        return JsonResponse({"ok": True, "message": "Profil berhasil diperbarui"}, status=200)

@login_required
def admin_change_status(request, id):
    import json
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    
    # Hanya admin yang boleh mengubah status sisanya permission denied
    if request.user.role != "admin":
        return JsonResponse({"ok": False, "message": "Permission denied"}, status=403)
    
    # Ambil data JSON dari request body
    data = json.loads(request.body)
    new_status = data.get("status") # Ambil status baru 
    
    STATUS_CHOICES = ['active', 'suspended', 'banned'] # Adalah daftar status yang valid

    # Jika status invalid maka error
    if new_status not in STATUS_CHOICES:
        return JsonResponse({"ok": False, "message": "Invalid status"}, status=400)
    # Jika valid maka
    try:
        # Ambil user berdasarkan id
        user = User.objects.get(pk=id)

        # Ambil profile user jika ada
        profile = getattr(user, 'profile', None)
        if not profile:
            return JsonResponse({"ok": False, "message": "Profile not found"}, status=404)
        
        # Ubah dan save perubahan status
        profile.status = new_status
        profile.save()
        return JsonResponse({"ok": True, "message": f"Status berhasil diubah menjadi {new_status}"})
    except User.DoesNotExist: # Jika user tidak ditemukan 
        return JsonResponse({"ok": False, "message": "User not found"}, status=404)
    
@login_required
def delete_profile(request, id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)

    # Ambil user berdasarkan UUID
    user = get_object_or_404(User, id=id)

    # Ambil profile user tsb
    profile = getattr(user, "profile", None)

    # Hanya pemilik sendiri atau admin
    if request.user != user and request.user.role != "admin":
        return JsonResponse({
            "ok": False,
            "message": "Anda tidak memiliki izin untuk menghapus profil ini."
        }, status=403)

    try:
        user.delete()

        if request.user == user:
            logout_user(request)

        return JsonResponse({
            "ok": True,
            "message": "Profil dan akun pengguna berhasil dihapus."
        })
    except Exception:
        return JsonResponse({
            "ok": False,
            "message": "Terjadi kesalahan saat menghapus profil."
        }, status=500)

def current_user_json(request):
    user = request.user
    profile = getattr(user, "profile", None)
    login_page = reverse("authentication:login") 
    
    if not user.is_authenticated:
        # Anonymous user akan redirect ke login
        return JsonResponse({
            "authenticated": False,
            "username": "Anonymous",
            "email": "",
            "role": "anonymous",
            "id": None,
            "profile_picture": static("images/default-profile-picture.png"),
            "menu": [
                {"name": "📷 Profil", "url": login_page},
                {"name": "🎫 Tiket Saya", "url": login_page},
                {"name": "📊 Analisis", "url": login_page},
            ]
        })
    
    # Tentukan profile picture & main profile URL
    if user.role == "admin":
        profile_picture_url = static("images/Admin.png")
        my_profile_url = reverse("profiles:admin_view")
        menu = [
            {"name": "📷 Profil", "url": my_profile_url},
            {"name": "📊 Analisis", "url": reverse("reviews:admin_analytics_page")},
        ]
    elif user.role == "journalist":
        profile_picture_url = static("images/Journalist.png")
        my_profile_url = reverse("profiles:journalist_view")
        menu = [
            {"name": "📷 Profil", "url": my_profile_url},
        ]
    else:  
        profile_picture_url = profile.profile_picture.url if profile and profile.profile_picture else static("images/default-profile-picture.png")
        my_profile_url = reverse("profiles:user_view", args=[user.id])
        menu = [
            {"name": "📷 Profil", "url": my_profile_url},
            {"name": "🎫 Tiket Saya", "url": reverse("profiles:user_tickets_page", args=[user.id])},
            {"name": "📊 Analisis", "url": reverse("reviews:user_analytics_page")},
        ]
    
    return JsonResponse({
        "authenticated": True,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "id": str(user.id),
        "profile_picture": profile_picture_url,
        "menu": menu,
    })

@login_required
def user_tickets_page(request, id):
    return render(request, "tickets.html", {})

@login_required
def user_tickets_json(request, id):
    """Ambil semua tiket user yang sudah dibayar (CONFIRMED)."""
    if request.user.role != "user" or request.user.id != id:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    tickets = (
        Ticket.objects
        .select_related("booking", "ticket_type__match", "ticket_type__match__home_team", "ticket_type__match__away_team")
        .filter(booking__user_id=id, booking__status="CONFIRMED")
        .order_by("-generated_at")
    )

    results = []
    for t in tickets:
        tt = t.ticket_type
        match = tt.match
        raw = f"{t.ticket_id}:{t.generated_at.timestamp()}"
        barcode_code = hashlib.sha1(raw.encode()).hexdigest()[:16].upper()

        results.append({
            "ticket_id": str(t.ticket_id),
            "match_id": str(match.id),
            "seat_category": tt.seat_category,
            "match_home": getattr(match.home_team, "name", "-"),
            "match_away": getattr(match.away_team, "name", "-"),
            "home_logo": match.home_team.display_logo_url if match.home_team else None,
            "away_logo": match.away_team.display_logo_url if match.away_team else None,
            "venue": getattr(match.venue, "name", "-"),
            "date": match.date.strftime("%d %b %Y, %H:%M") if match.date else "-",
            "match_iso": match.date.isoformat() if match.date else None,
            "barcode_code": barcode_code,
            "is_used": t.is_used,
            "generated_at": t.generated_at.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({"tickets": results})

# ======================================== Flutter
@csrf_exempt
def create_profile_flutter(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)

    # Cari user session
    user = request.user if request.user.is_authenticated else None

    # Fallback ke username dari POST
    if user is None:
        username = request.POST.get("username")
        if username:
            try:
                user = User.objects.get(username=username)
                print(f"DEBUG: Fallback found user = {user}")
            except User.DoesNotExist:
                return JsonResponse({
                    "success": False,
                    "message": "User tidak ditemukan"
                }, status=404)

    # Kalo user tidak ada
    if user is None:
        return JsonResponse({
            "success": False,
            "message": "User tidak terautentikasi. Silakan login terlebih dahulu."
        }, status=401)

    # Admin Journalist tdk perlu bikin profile
    if user.role in ["admin", "journalist"]:
        return JsonResponse({
            "success": False,
            "message": "Admin/Journalist tidak perlu membuat profil pengguna."
        }, status=403)

    # Validasi supaya profile tidak lebih dari satu
    if hasattr(user, 'profile'):
        return JsonResponse({"ok": False, "message": "Profil sudah terdaftar sebelumnya."}, status=400)

    # Ambil data POST-data 
    profile_picture = request.FILES.get("profile_picture")
    date_of_birth = request.POST.get("date_of_birth")
    phone_number  = request.POST.get("phone")

    # Buat profile sesuai dengan input dari form user
    Profile.objects.create(
        user=user,
        date_of_birth=date_of_birth,
        profile_picture=profile_picture,
        status="active",
    )

    # Sesuaikan user sesuai dengan input dari form user
    user.phone = phone_number
    user.profile_completed = True
    user.save()

    return JsonResponse({"ok": True, "message": "Profil berhasil didaftarkan."}, status=201)

@csrf_exempt
def admin_change_status_flutter(request, id):
    import json
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)
    
    # Hanya admin yang boleh mengubah status sisanya permission denied
    if request.user.role != "admin":
        return JsonResponse({"ok": False, "message": "Permission denied"}, status=403)
    
    # Ambil data JSON dari request body
    data = json.loads(request.body)
    new_status = data.get("status") # Ambil status baru 
    
    STATUS_CHOICES = ['active', 'suspended', 'banned'] # Adalah daftar status yang valid

    # Jika status invalid maka error
    if new_status not in STATUS_CHOICES:
        return JsonResponse({"ok": False, "message": "Invalid status"}, status=400)
    # Jika valid maka
    try:
        # Ambil user berdasarkan id
        user = User.objects.get(pk=id)

        # Ambil profile user jika ada
        profile = getattr(user, 'profile', None)
        if not profile:
            return JsonResponse({"ok": False, "message": "Profile not found"}, status=404)
        
        # Ubah dan save perubahan status
        profile.status = new_status
        profile.save()
        return JsonResponse({"ok": True, "message": f"Status berhasil diubah menjadi {new_status}"})
    except User.DoesNotExist: # Jika user tidak ditemukan 
        return JsonResponse({"ok": False, "message": "User not found"}, status=404)

@csrf_exempt
def delete_profile_flutter(request, id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Method not allowed"}, status=405)

    # Ambil user berdasarkan UUID
    user = get_object_or_404(User, id=id)

    # Ambil profile user tsb
    profile = getattr(user, "profile", None)

    # Hanya pemilik sendiri atau admin
    if request.user != user and request.user.role != "admin":
        return JsonResponse({
            "ok": False,
            "message": "Anda tidak memiliki izin untuk menghapus profil ini."
        }, status=403)

    try:
        user.delete()

        if request.user == user:
            flutter_logout(request)

        return JsonResponse({
            "ok": True,
            "message": "Profil dan akun pengguna berhasil dihapus."
        })
    except Exception:
        return JsonResponse({
            "ok": False,
            "message": "Terjadi kesalahan saat menghapus profil."
        }, status=500)

@csrf_exempt
def edit_profile_flutter(request, id):
    user = get_object_or_404(User, pk=id)
    
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "Invalid method"}, status=400)

    # Ambil field dari multipart
    username = request.POST.get("username")
    email = request.POST.get("email")
    first_name = request.POST.get("first_name")
    last_name = request.POST.get("last_name")
    phone = request.POST.get("phone")
    dob = request.POST.get("date_of_birth")
    profile_picture = request.FILES.get("profile_picture")

    # UPDATE USER
    if username:
        user.username = username.strip()

    if email:
        user.email = email.strip()

    if first_name:
        user.first_name = first_name.strip()

    if last_name:
        user.last_name = last_name.strip()

    if phone:
        user.phone = phone.strip()

    user.save()

    # UPDATE PROFILE
    profile = getattr(user, "profile", None)
    if not profile:
        profile = Profile.objects.create(user=user)

    if dob:
        profile.date_of_birth = dob

    if profile_picture:
        profile.profile_picture = profile_picture

    profile.save()

    return JsonResponse({
        "ok": True,
        "message": "Profil berhasil diperbarui",
        "updated": {
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": str(user.phone) if user.phone else None,
            "date_of_birth": str(profile.date_of_birth),
            "profile_picture": profile.profile_picture.url if profile.profile_picture else None
        }
    }, status=200)