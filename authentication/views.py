from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from authentication.forms import RegisterForm
import datetime
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.html import strip_tags
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from authentication.models import User
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

def register_user(request):
    
    if request.user.is_authenticated:
        return redirect(reverse("matches:calendar"))
    
    form = RegisterForm()
    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            response = JsonResponse({
                "status": "success",
                "message": "Registration successful",
                "redirect_url": reverse("profiles:create_profile")
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
    if request.user.is_authenticated:
        return redirect(reverse("matches:calendar"))
    
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Cek status profil kalau role = user
            if hasattr(user, "profile"):
                profile_status = user.profile.status
                if profile_status == "banned":
                    return JsonResponse({
                        "status": "banned",
                        "message": "Akun Anda telah diblokir. Hubungi admin di l1gapass@outlook.com."
                    }, status=403)
                elif profile_status == "suspended":
                    warning_msg = "Akun Anda sedang ditangguhkan sementara. Beberapa fitur (seperti komentar) dinonaktifkan."
                else:
                    warning_msg = None
            else:
                profile_status = None
                warning_msg = None

            # Login user
            login(request, user)

            if user.role == "user":
                if hasattr(user, 'profile'):
                    redirect_url = reverse("matches:calendar")
                else:
                    redirect_url = reverse("profiles:create_profile")
            else:
                redirect_url = reverse("matches:calendar")

            response = JsonResponse({
                "status": "success",
                "message": "Login successful",
                "redirect_url": redirect_url,
                "warning": warning_msg,
                "profile_status": profile_status
            })
            response.set_cookie('last_login', str(datetime.datetime.now()))
            return response

        return JsonResponse({
            "status": "error",
            "errors": form.errors
        }, status=400)

    form = AuthenticationForm()
    return render(request, "login.html", {"form": form})

@require_POST
def logout_user(request):
    logout(request)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "status": "success",
            "message": "Berhasil logout!",
            "redirect_url": "/"
        })
    return JsonResponse({
        "status": "success",
        "redirect_url": "/"
    })

@csrf_exempt
def google_login(request):
    if request.method == "POST":
        try:
            token = request.POST.get("credential")
            if not token:
                return JsonResponse({"status": "error", "message": "Missing credential."}, status=400)

            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), settings.GOOGLE_CLIENT_ID
            )

            email = idinfo.get("email")
            google_sub = idinfo.get("sub")

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

            # Cek status profile (jika ada)
            profile_status = getattr(getattr(user, "profile", None), "status", "active")
            if profile_status == "banned":
                return JsonResponse({
                    "status": "banned",
                    "message": "Akun Anda telah diblokir. Hubungi admin di l1gapass@outlook.com."
                }, status=403)

            elif profile_status == "suspended":
                warning_msg = "Akun Anda sedang ditangguhkan sementara. Beberapa fitur dinonaktifkan."
            else:
                warning_msg = None

            login(request, user)

            if user.role == "user":
                if hasattr(user, 'profile'):
                    redirect_url = reverse("matches:calendar")
                else:
                    redirect_url = reverse("profiles:create_profile")
            else:
                redirect_url = reverse("matches:calendar")

            response = JsonResponse({
                "status": "success",
                "message": "Google login successful",
                "redirect_url": redirect_url,
                "warning": warning_msg,
                "profile_status": profile_status
            })
            response.set_cookie("last_login", str(datetime.datetime.now()))
            return response

        except ValueError as e:
            return JsonResponse({"status": "error", "message": f"Invalid token: {e}"}, status=401)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)