import uuid
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.contrib.auth import get_user_model 
from profiles.forms import UserEditForm
from profiles.models import TicketPurchase, MatchReview, Profile

User = get_user_model()

# Fungsi untuk pengecekan role
def is_admin(user):
    # admin_id = uuid.UUID('62250f66-62e4-47a3-a2b5-43717195c820') # DEBUG ADMIN
    # return (user.is_authenticated and user.profile.role == 'admin') or (user.id == admin_id) # DEBUG ADMIN
    return (user.is_authenticated and user.profile.role == 'admin')

def is_journalist(user):
    return user.is_authenticated and user.profile.role == 'journalist'

def is_user(user):
    return user.is_authenticated and user.profile.role == 'user'

# Tampilan untuk profile masing-masing role
@login_required(login_url='/login')
def user_view(request, id):
    user = get_object_or_404(User, id=id)
    profile = user.profile
    context = {
        'profile_picture': profile.profile_picture,
        'full_name': profile.full_name,
        'username': profile.username,
        'email': profile.email,
        'phone_number': profile.phone_number,
        'date_of_birth': profile.date_of_birth,
    }
    return render(request, 'user.html', context)
    
@login_required(login_url='/login')
@user_passes_test(is_admin)
def admin_view(request):
    profile = request.user.profile
    context = {
        'profile_picture': profile.profile_picture,
        'username': profile.username,
    }
    return render(request, 'admin.html', context)

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
    return render(request, 'journalist.html', context)

@login_required(login_url='/login')
@user_passes_test(is_admin)
def admin_user_edit(request, id):
    user = get_object_or_404(User, id=id)
    profile = getattr(user, 'profile', None)
    purchases = TicketPurchase.objects.filter(user=user)
    reviews = MatchReview.objects.filter(user=user)

    # Untuk mengubah status dari user
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Profile.STATUS_CHOICES):
            profile.status = new_status
            profile.save()
            return redirect('profile:admin_user_edit', id=user.id)

    context = {
        'admin': request.user,
        'user': user,
        'user_profile': profile,
        'purchases': purchases,
        'reviews': reviews,
        'user_status': Profile.STATUS_CHOICES,
    }

    return render(request, 'admin_edit_user.html', context)

# def user_edit() # Draft untuk user edit