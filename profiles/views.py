from django.middleware.csrf import get_token
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from dotenv import get_key
from authentication.models import User
from profiles.models import AdminJournalistProfile, Profile

# Create profile untuk user yang baru registrasi
@login_required
def create_profile(request):
    if request.method == "GET":
        return render(request, "create_profile.html")
    elif request.method == "POST":
        # Validasi supaya profile tidak lebih dari satu
        if (hasattr(request.user, 'profile')):
            return HttpResponse("PROFILE ALREADY EXISTS", status=400)
        
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

        return HttpResponse(b"PROFILE CREATED", status=201)

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

# Menampilkan JSON admin dan journalist (tanpa argumen id)
@login_required
def show_json_admin_journalist(request):
    try:
        user = request.user
        if user.role == 'admin' or user.role == 'journalist':
            profile = getattr(user, 'adminjournalistprofile', None)
            data = {
                "username": user.username,
                "profile_picture": profile.profile_picture if profile and profile.profile_picture else None
            }
            return JsonResponse(data)
        else:
            return JsonResponse({'error' : 'Forbidden'}, status=403)
    except Exception:
        return JsonResponse({'error': 'Internal Server Error'}, status=500)

# JSON untuk search dan filter pada admin view
def admin_view_json(request):
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
@login_required
def admin_view(request):
    return render(request, "admin_profile.html")

# Untuk menampilkan journalist_profile.html
@login_required
def journalist_view(request):
    return render(request, "journalist_profile.html")

# Edit user profile untuk user
@login_required
def edit_profile_for_user(request, id):
    user = get_object_or_404(User, pk=id)

    # Sebagai prevention supaya user tidak bisa mengedit profile user yang lain
    if request.user != user:
        return HttpResponseForbidden("Kamu tidak memiliki izin untuk mengedit.")
    
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

        return HttpResponse(b"PROFILE UPDATED", status=200)

@login_required
def admin_change_status(request, id):
    import json
    
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    if request.user.role != "admin":
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    data = json.loads(request.body)
    new_status = data.get("status")
    
    STATUS_CHOICES = ['active', 'suspended', 'banned']

    if new_status not in STATUS_CHOICES:
        return JsonResponse({"error": "Invalid status"}, status=400)
    
    try:
        user = User.objects.get(pk=id)
        profile = getattr(user, 'profile', None)
        if not profile:
            return JsonResponse({"error": "Profile not found"}, status=404)
        
        profile.status = new_status
        profile.save()
        return JsonResponse({"status": profile.status})
    except User.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)
