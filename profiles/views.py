from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
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

# Menampilkan JSON by id
@login_required
def show_json_by_id(request, id):
    try:
        user = User.objects.get(pk=id)
        if user.role == 'admin' or user.role == 'journalist':
            profile = getattr(user, 'adminjournalistprofile', None)
            data = {
                "username": user.username,
                "profile_picture" : profile.profile_picture if profile and profile.profile_picture else None
            }
            return JsonResponse(data)
        else:
            profile = getattr(user, 'profile', None)
            data = {
                "full_name": profile.full_name,
                "username": user.username,
                "email": user.email,
                "phone": str(user.phone) if user.phone else None,
                "date_of_birth": profile.date_of_birth.strftime('%Y-%m-%d') if profile and profile.date_of_birth else None,
                "profile_picture": profile.profile_picture.url if profile and profile.profile_picture else None,
            }
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

# Untuk menampilkan user_profile.html
@login_required
def user_view(request, id):
    return render(request, "user_profile.html", {"id":id})

# TODO: hardcode admin dan journalist
# TODO: fix kan yang dibawah setelah hardcode
# Untuk menampilkan admin_profile.html
@login_required
def admin_view(request):
    return render(request, "admin_profile.html")

# Untuk menampilkan journalist_profile.html
@login_required
def journalist_view(request):
    return render(request, "journalist_profile.html")
