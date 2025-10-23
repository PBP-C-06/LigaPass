from django.shortcuts import render
from django.http import JsonResponse
from django.templatetags.static import static

def current_user_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({"authenticated": False})

    user = request.user
    profile = getattr(user, "profile", None)

    # Tentukan url profile picture berdasarkan role
    if user.role == "admin":
        profile_picture_url = static("images/Admin.png")

    elif user.role == "journalist":
        profile_picture_url = static("images/Journalist.png")

    else:
        # Jika user biasa maka ambil dari media
        if profile and profile.profile_picture:
            profile_picture_url = profile.profile_picture.url
        else: # Tetapi jika tidak ditemukan tetap ambil dari static 
            profile_picture_url = static("images/default-profile-picture.png")

    return JsonResponse({
        "authenticated": True,
        "username": user.username,
        "role": user.role,
        "id": str(user.id),
        "profile_picture": profile_picture_url,
    })