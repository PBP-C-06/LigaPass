from django.shortcuts import render, get_object_or_404, redirect
from .models import News, CATEGORY_CHOICES
from .forms import NewsForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from datetime import datetime
from django.forms.widgets import ClearableFileInput
from django.http import JsonResponse

def is_journalist(user):
    return getattr(user, "is_authenticated", False) and getattr(user, "role", None) == "journalist"

def latest_news_snippet(request):
    latest_news = News.objects.order_by('-created_at')[:3]  # Ambil 3 berita terbaru
    return render(request, 'news/latest_news_snippet.html', {'latest_news': latest_news})

class PlainFileInput(ClearableFileInput):
    template_name = 'widgets/plain_file_input.html'

def news_list(request):
    news = News.objects.all()
    query = request.GET.get('search')
    category = request.GET.get('category')
    is_featured = request.GET.get('is_featured')
    sort = request.GET.get('sort')

    if query:
        news = news.filter(title__icontains=query)
    if category:
        news = news.filter(category=category)
    if is_featured in ['true', 'false']:
        news = news.filter(is_featured=(is_featured == 'true'))

    if sort in ['created_at', 'edited_at', 'news_views']:
        news = news.order_by(f'-{sort}')

    return render(request, 'news/news_list.html', {
        'news_list': news,
        'is_journalist': is_journalist(request.user),
        'category_choices': CATEGORY_CHOICES,
    })

def news_detail(request, pk):
    news = get_object_or_404(News, pk=pk)
    news.news_views += 1
    news.save(update_fields=["news_views"])
    recommended_news = News.objects.filter(~Q(pk=pk)).order_by('-created_at')[:3]
    return render(request, 'news/news_detail.html', {
        'news': news,
        'is_journalist': is_journalist(request.user),
        'recommended_news': recommended_news,
    })

@login_required
@user_passes_test(is_journalist)
def news_create(request):
    if request.method == 'POST':
        form = NewsForm(request.POST, request.FILES)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            news.save()
            messages.success(request, "Berita berhasil dibuat!")
            return redirect('news:news_list')
    else:
        form = NewsForm()
    return render(request, 'news/news_form.html', {'form': form, 'is_create': True})

@login_required
@user_passes_test(is_journalist)
def news_edit(request, pk):
    news = get_object_or_404(News, pk=pk, author=request.user)

    if request.method == 'POST':
        form = NewsForm(request.POST, request.FILES, instance=news)

        if form.is_valid():
            # Handle delete thumbnail via custom JS
            if request.POST.get("delete_thumbnail") == "true":
                if news.thumbnail:
                    news.thumbnail.delete(save=False)
                    news.thumbnail = None

            news = form.save(commit=False)
            news.edited_at = datetime.now()
            news.save()
            messages.success(request, "Berita berhasil diedit!")
            return redirect('news:news_detail', pk=pk)
    else:
        form = NewsForm(instance=news)

    return render(request, 'news/news_form.html', {
        'form': form,
        'is_create': False,
        'news': news
    })

@login_required
@user_passes_test(is_journalist)
def news_delete(request, pk):
    news = get_object_or_404(News, pk=pk, author=request.user)

    if request.method == 'POST':
        news.delete()

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        messages.success(request, 'Berita berhasil dihapus.')
        return redirect('news:news_list')

    return render(request, 'news/news_confirm_delete.html', {'news': news})