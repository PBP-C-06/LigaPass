from django.shortcuts import render, get_object_or_404, redirect
from .models import News, CATEGORY_CHOICES, Comment
from .forms import NewsForm, CommentForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count
from datetime import datetime
from django.forms.widgets import ClearableFileInput
from django.http import JsonResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

# Override tampilan input file menggunakan template kustom (plain_file_input.html)
class PlainFileInput(ClearableFileInput):
    template_name = 'widgets/plain_file_input.html'

# Cek apakah user memiliki role 'journalist'
def is_journalist(user):
    return user.role == 'journalist'

# Snippet berita terbaru untuk bagian kecil halaman 
def latest_news_snippet(request):
    latest_news = News.objects.order_by('-created_at')[:3]  # Ambil 3 berita terbaru
    return render(request, 'news/latest_news_snippet.html', {'latest_news': latest_news})

# Menampilkan daftar semua berita
@login_required
def news_list(request):
    news = News.objects.all()
    query = request.GET.get('search')
    category = request.GET.get('category')
    is_featured = request.GET.get('is_featured')
    sort = request.GET.get('sort')

    # Filter melalui query string
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

@login_required
def news_detail(request, pk):
    news = get_object_or_404(News, pk=pk)
    news.news_views += 1
    news.save(update_fields=["news_views"])

    sort = request.GET.get('sort', 'latest')

    # Ambil semua komentar
    all_comments = Comment.objects.filter(news=news).prefetch_related(
        'likes',
        'replies',
        'replies__likes',
        'replies__replies',
    )

    # Filter root comments
    if sort == 'popular':
        root_comments = all_comments.filter(parent=None).annotate(
            total_likes=Count('likes')
        ).order_by('-total_likes', '-created_at')
    else:
        root_comments = all_comments.filter(parent=None).order_by('-created_at')

    # Set flag like user
    def set_user_like_flags(comments, depth=0, max_depth=5):
        if depth > max_depth:
            return
        for comment in comments:
            comment.user_has_liked = comment.is_liked_by(request.user)
            if hasattr(comment, 'replies'):
                set_user_like_flags(comment.replies.all(), depth + 1, max_depth)

    set_user_like_flags(root_comments)

    if request.headers.get("x-requested-with") == "XMLHttpRequest" and request.method == "GET":
        comments_html = render_to_string("news/comment_list.html", {
            "comments": root_comments,
            "request": request
        })

        return JsonResponse({
            "success": True,
            "comments_html": comments_html
        })
    
    comment_form = CommentForm()

    # Tangani AJAX POST untuk komentar utama atau balasan
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            parent_id = request.POST.get("parent_id")
            parent = Comment.objects.filter(id=parent_id).first() if parent_id else None
            new_comment = Comment.objects.create(
                news=news,
                user=request.user,
                content=comment_form.cleaned_data['content'],
                parent=parent
            )

            new_comment.user_has_liked = False  # Baru dibuat, belum dilike

            html = render_to_string("news/comment_tree.html", {
                'comment': new_comment,
                'is_child': bool(parent),
                'request': request
            })

            total_comments = Comment.objects.filter(news=news).count()

            return JsonResponse({
                'success': True,
                'comment_html': html,
                'total_comments': total_comments,
            })
        else:
            return JsonResponse({'success': False, 'error': 'Komentar tidak valid'}, status=400)

    elif request.method == 'POST':
        # Fallback jika bukan AJAX
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            Comment.objects.create(
                news=news,
                user=request.user,
                content=comment_form.cleaned_data['content'],
            )
            return redirect('news:news_detail', pk=pk)
        else:
            return redirect('news:news_detail', pk=pk)

    total_comments = all_comments.count()
    recommended_news = News.objects.filter(~Q(pk=pk)).order_by('-created_at')[:3]

    return render(request, 'news/news_detail.html', {
        'news': news,
        'is_journalist': is_journalist(request.user),
        'recommended_news': recommended_news,
        'comment_form': comment_form,
        'total_comments': total_comments,
        'comments': root_comments,
        'sort': sort,
    })

@login_required
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    user = request.user

    if comment.likes.filter(id=user.id).exists():
        comment.likes.remove(user)
        liked = False
    else:
        comment.likes.add(user)
        liked = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'liked': liked,
            'like_count': comment.likes.count()
        })

    return redirect('news:news_detail', pk=comment.news.pk)


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    comment.delete()
    
    total_comments = Comment.objects.filter(news=comment.news).count()
    return JsonResponse({'success': True, 'total_comments': total_comments})

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