from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from authentication.forms import RegisterForm
import datetime
from django.http import JsonResponse
from django.urls import reverse
from django.utils.html import strip_tags
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from authentication.models import User
from django.views.decorators.csrf import csrf_exempt

def register_user(request):
    form = RegisterForm()
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            response = JsonResponse({
                "status": "success",
                "message": "Registration successful",
                "redirect_url": reverse("main:show_main")
            })
            response.set_cookie('last_login', str(datetime.datetime.now()))
            return response
        
        return JsonResponse({
            "status": "error",
            "errors": form.errors
        }, status=400)
    return render(request, "register.html", {"form": form})

# Non Google login
def login_user(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            response = JsonResponse({
                "status": "success",
                "message": "Login successful",
                "redirect_url": reverse("main:show_main")
            })
            response.set_cookie('last_login', str(datetime.datetime.now()))
            return response
        return JsonResponse({
            "status": "error",
            "errors": form.errors
        }, status=400)
    form = AuthenticationForm()
    return render(request, "login.html", {"form": form})

def logout_user(request):
    if request.method == "POST":
        logout(request)
        response = JsonResponse({
            "status": "success",
            "message": "You have been logged out successfully.",
            "redirect_url": reverse("authentication:login"),
        })
        response.delete_cookie("last_login")
        return response

    logout(request)
    response = redirect("authentication:login")
    response.delete_cookie("last_login")
    return response

@csrf_exempt
def google_login(request):
    """
    Handle Google OAuth login (redirect-based, bukan AJAX).
    """
    if request.method == "POST":
        try:
            # Ambil credential dari form POST
            token = request.POST.get("credential")
            if not token:
                return JsonResponse({"status": "error", "message": "Missing credential."}, status=400)

            # Verifikasi token Google
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), settings.GOOGLE_CLIENT_ID
            )

            email = idinfo.get("email")
            google_sub = idinfo.get("sub")

            # Buat user baru kalau belum ada
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": email.split("@")[0],
                    "first_name": idinfo.get("given_name", ""),
                    "last_name": idinfo.get("family_name", ""),
                    "is_google_account": True,
                    "google_sub": google_sub,
                },
            )

            login(request, user)
            response = redirect("main:show_main")
            response.set_cookie("last_login", str(datetime.datetime.now()))
            return response

        except ValueError as e:
            return JsonResponse({"status": "error", "message": f"Invalid token: {e}"}, status=401)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)
