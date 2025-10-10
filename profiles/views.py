from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model 
from django.views.decorators.csrf import csrf_exempt

User = settings.AUTH_USER_MODEL

# Fungsi untuk pengecekan role
def is_admin(user):
    return user.is_authenticated and user.profile.role == 'admin'

def is_journalist(user):
    return user.is_authenticated and user.profile.role == 'journalist'

def is_user(user):
    return user.is_authenticated and user.profile.role == 'user'

# Tampilan untuk profile masing-masing role
@login_required(login_url='/login')
def user_view(request):
    profile = request.user.profile
    context = {
        'profile_picture': profile.profile_picture,
        'full_name': profile.full_name,
        'username': profile.username,
        'email': profile.email,
        'phone_number': profile.phone_number,
        'date_of_birth': profile.date_of_birth,
    }
    return render(request, 'user_profile.html', context)
    
@login_required(login_url='/login')
@user_passes_test(is_admin)
def admin_view(request):
    profile = request.user.profile
    context = {
        'profile_picture': profile.profile_picture,
        'username': profile.username,
    }
    return render(request, 'admin_profile.html', context)

@login_required(login_url='/login')
@user_passes_test(is_journalist)
def journalist_view(request):
    profile = request.user.profile
    context = {
        'profile_picture': profile.profile_picture,
        'username': profile.username,
        'total_views': profile.total_journalist_views,
        'total_news': profile.total_journalist_news,
    }
    return render(request, 'journalist_profile.html', context)

@csrf_exempt
def show_json(request):
    User = get_user_model() 
    user_list = User.objects.all().select_related('profile') 
    data = []
    for user in user_list:
        try:
            profile = user.profile
        except AttributeError:
            profile = None 
        if profile:
            user_data = {
                'id': user.pk, 
                'username': profile.username,
                'full_name': profile.full_name,
                'email': profile.email,
                'role': profile.role,
                'profile_picture_url': profile.profile_picture.url if profile.profile_picture else None,
                'date_of_birth': profile.date_of_birth,
                'total_journalist_views': profile.total_journalist_views,
                'total_journalist_news': profile.total_journalist_news,
            }
        else:
            user_data = {
                'id': user.pk, 
                'username': user.username, 
                'full_name': None,
                'email': user.email, 
                'role': 'user', 
                'profile_picture_url': None,
                'date_of_birth': None,
                'total_journalist_views': None,
                'total_journalist_news': None,
            }
        data.append(user_data)
    return JsonResponse(data, safe=False)

# TODO:
# Untuk edit profile user
# Tampilan untuk admin ke user
# @user_passes_test(is_admin)
# def admin_user_view(request, user_id):
#     context = {
#         'user': 'soon',
#         'purchase_history': 'soon',
#         'review_history': 'soon',
#     }
#     return render(request, 'admin_user_profile.html', context)

