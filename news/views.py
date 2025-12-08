from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404, redirect
from .models import News, CATEGORY_CHOICES, Comment
from .forms import NewsForm, CommentForm
from profiles.utils import get_user_status
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count
from datetime import datetime
from django.forms.widgets import ClearableFileInput
from django.http import JsonResponse, HttpResponseForbidden
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_GET
from django.conf import settings
from django.core.serializers import serialize
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateformat import DateFormat
from django.contrib.sites.shortcuts import get_current_site
import json
import base64
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


# Override tampilan input file menggunakan template kustom
class PlainFileInput(ClearableFileInput):
    template_name = 'widgets/plain_file_input.html'

# Cek apakah user memiliki role 'journalist'
def is_journalist(user):
    return getattr(user, "is_authenticated", False) and getattr(user, "role", None) == "journalist"

# Snippet berita terbaru untuk menampilkan 3 berita terbaru di sidebar atau widget lain
def latest_news_snippet(request):
    latest_news = News.objects.order_by('-created_at')[:3]  # Ambil 3 berita terbaru
    return render(request, 'news/latest_news_snippet.html', {'latest_news': latest_news})

# Menampilkan daftar semua berita dengan filter & sort
def news_list(request):
    news = News.objects.all() # Ambil semua berita

    # Ambil parameter dari query string untuk search dan filter
    query = request.GET.get('search')
    category = request.GET.get('category')
    is_featured = request.GET.get('is_featured')
    sort = request.GET.get('sort')

    # Filter melalui pencarian judul
    if query:
        news = news.filter(title__icontains=query)
    # Filter melalui kategori
    if category:
        news = news.filter(category=category)
    # Filter melalui unggulan (featured)
    if is_featured in ['true', 'false']:
        news = news.filter(is_featured=(is_featured == 'true'))

    # Sorting berdasarkan field tertentu
    if sort in ['created_at', 'edited_at', 'news_views']:
        news = news.order_by(f'-{sort}')

    # Tampilkan halaman list berita
    return render(request, 'news/news_list.html', {
        'news_list': news,
        'is_journalist': is_journalist(request.user),
        'category_choices': CATEGORY_CHOICES,
    })

# Menampilkan detail berita dan komentarnya
def news_detail(request, pk):
    news = get_object_or_404(News, pk=pk) # Ambil berita berdasarkan primary key
    news.news_views += 1 # Tambahkan view count 
    news.save(update_fields=["news_views"]) # Simpan hanya field 'news_views'

    # Urutkan komentar
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

    # Set flag user menyukai komentar tertentu (dan reply-nya)
    def set_user_like_flags(comments, depth=0, max_depth=5):
        if depth > max_depth:
            return
        for comment in comments:
            comment.user_has_liked = comment.is_liked_by(request.user)
            if hasattr(comment, 'replies'):
                set_user_like_flags(comment.replies.all(), depth + 1, max_depth)

    set_user_like_flags(root_comments) # Tandai komentar yang dilike user

    # request AJAX untuk load komentar (GET)
    if request.headers.get("x-requested-with") == "XMLHttpRequest" and request.method == "GET":
        comments_html = render_to_string("news/comment_list.html", {
            "comments": root_comments,
            "request": request
        })

        return JsonResponse({
            "success": True,
            "comments_html": comments_html
        })
    
    comment_form = CommentForm() # Buat form kosong untuk komentar

    # AJAX POST untuk komentar utama atau balasan
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Login diperlukan untuk komentar.'}, status=403) # Cek autentikasi user
        if get_user_status(request.user) == "suspended":
            return JsonResponse({
                'success': False,
                'error': 'Anda tidak dapat memposting komentar karena akun Anda ditangguhkan'
            }, status=403)
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            parent_id = request.POST.get("parent_id")
            parent = Comment.objects.filter(id=parent_id).first() if parent_id else None
            # Buat komentar baru
            new_comment = Comment.objects.create(
                news=news,
                user=request.user,
                content=comment_form.cleaned_data['content'],
                parent=parent
            )

            new_comment.user_has_liked = False  # Baru dibuat, belum dilike

            # Render komentar jadi HTML
            html = render_to_string("news/comment_tree.html", {
                'comment': new_comment,
                'is_child': bool(parent),
                'request': request
            })

            total_comments = Comment.objects.filter(news=news).count() # Hitung ulang total komentar

            return JsonResponse({
                'success': True,
                'comment_html': html,
                'total_comments': total_comments,
            })
        else:
            return JsonResponse({'success': False, 'error': 'Komentar tidak valid'}, status=400)

    elif request.method == 'POST':
        if not request.user.is_authenticated:  # Cek autentikasi user
            return redirect(settings.LOGIN_URL)
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

    total_comments = all_comments.count() # Hitung total komentar
    recommended_news = News.objects.filter(~Q(pk=pk)).order_by('-created_at')[:3] # Berita lain

    return render(request, 'news/news_detail.html', {
        'news': news,
        'is_journalist': is_journalist(request.user),
        'recommended_news': recommended_news,
        'comment_form': comment_form,
        'total_comments': total_comments,
        'comments': root_comments,
        'sort': sort,
    })

# View untuk like / unlike komentar
@login_required
def like_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    user = request.user

    if get_user_status(request.user) == "suspended":
            return JsonResponse({
                'success': False,
                'error': 'Anda tidak dapat memposting komentar karena akun Anda ditangguhkan'
            }, status=403)
    
    # Jika sudah dilike, hapus like
    if comment.likes.filter(id=user.id).exists():
        comment.likes.remove(user)
        liked = False
    else:
        comment.likes.add(user)
        liked = True

    # Jika request via AJAX, kembalikan hasil JSON
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'liked': liked,
            'like_count': comment.likes.count()
        })

    # Jika bukan AJAX, redirect balik ke detail berita
    return redirect('news:news_detail', pk=comment.news.pk)

# View untuk menghapus komentar milik user sendiri
@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    comment.delete()
    
    total_comments = Comment.objects.filter(news=comment.news).count()  # Hitung total komentar
    return JsonResponse({'success': True, 'total_comments': total_comments})

# View untuk membuat berita baru (hanya jurnalis)
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

# View untuk mengedit berita (hanya jurnalis)
@login_required
@user_passes_test(is_journalist)
def news_edit(request, pk):
    news = get_object_or_404(News, pk=pk)
    is_owner = news.author == request.user

    if request.method == 'POST':
        form = NewsForm(request.POST, request.FILES, instance=news)

        if form.is_valid():
            # Handle delete thumbnail via custom JS
            if request.POST.get("delete_thumbnail") == "true":
                if news.thumbnail:
                    news.thumbnail.delete(save=False)
                    news.thumbnail = None

            news = form.save(commit=False)
            news.edited_at = datetime.now() # Set waktu edit sekarang
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

# View untuk menghapus berita (hanya pemilik)
@login_required
@user_passes_test(is_journalist)
def news_delete(request, pk):
    news = get_object_or_404(News, pk=pk)
    is_owner = news.author == request.user

    if request.method == 'POST':
        news.delete()

        # Jika AJAX, balas JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        # Jika bukan AJAX, redirect
        messages.success(request, 'Berita berhasil dihapus.')
        return redirect('news:news_list')

    # Jika GET, tampilkan halaman konfirmasi
    return render(request, 'news/news_confirm_delete.html', {'news': news})

# Fungsi utilitas untuk mengubah objek News menjadi dict siap di-JSON-kan
def serialize_news(news, request):
    # Build domain penuh
    domain = request.build_absolute_uri('/')[:-1]
    return {
        "id": news.id,
        "title": news.title,
        "content": news.content,
        "thumbnail": domain + news.thumbnail.url if news.thumbnail else '',
        "category": news.category,
        "is_featured": news.is_featured,
        "news_views": news.news_views,
        "created_at": DateFormat(news.created_at).format("Y-m-d H:i"),
    }

# Endpoint API (berbasis JSON) untuk daftar berita
def api_news_list(request):
    # Ambil semua News terlebih dahulu
    news = News.objects.all()

    # Ambil query string filter & sort seperti di view HTML
    query = request.GET.get('search')
    category = request.GET.get('category')
    is_featured = request.GET.get('is_featured')
    sort = request.GET.get('sort', 'created_at')

    # Filter berdasarkan judul jika ada query
    if query:
        news = news.filter(title__icontains=query)
    # Filter berdasarkan kategori jika ada
    if category:
        news = news.filter(category=category)
    # Filter is_featured jika nilainya 'true' atau 'false'
    if is_featured in ['true', 'false']:
        news = news.filter(is_featured=(is_featured == 'true'))
    # Sorting berdasarkan field yang diperbolehkan
    if sort in ['created_at', 'edited_at', 'news_views']:
        news = news.order_by(f'-{sort}')

    # Serialisasikan setiap objek News menggunakan fungsi serialize_news
    data = [serialize_news(n, request) for n in news]

    # Return JsonResponse dengan data list
    return JsonResponse(data, safe=False)

# Endpoint API untuk detail satu berita
def api_news_detail(request, pk):
    # Coba ambil berita berdasarkan pk
    try:
        news = News.objects.get(pk=pk)
    # Jika tidak ada, balas JSON error dengan status 404
    except News.DoesNotExist:
        return JsonResponse({"error": "Berita tidak ditemukan"}, status=404)

    # Tambah jumlah view setiap kali endpoint ini dipanggil
    news.news_views += 1
    # Simpan ke database, hanya field news_views yang diupdate
    news.save(update_fields=['news_views'])

    # Siapkan dictionary data untuk dikirim ke client
    data = {
        "id": news.id,
        "title": news.title,
        "content": news.content,
        "thumbnail": request.build_absolute_uri(news.thumbnail.url) if news.thumbnail else '',
        "category": news.category,
        "is_featured": news.is_featured,
        "news_views": news.news_views,
        "created_at": DateFormat(news.created_at).format("Y-m-d H:i"),
        "is_owner": news.author == request.user,
    }

    # Return JsonResponse dengan data
    return JsonResponse(data)

@csrf_exempt # Nonaktifkan CSRF
@require_http_methods(["GET", "POST"]) # Hanya mengizinkan method GET dan POST
# Endpoint API untuk mengambil dan membuat komentar berita
def api_news_comments(request, pk):
    # Ambil objek News, 404 jika tidak ada
    news = get_object_or_404(News, pk=pk)

    # Jika method POST, berarti client ingin menambahkan komentar baru
    if request.method == "POST":
        # Pastikan user sudah login
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Login diperlukan'}, status=403)
        
        # Cek status user (suspended atau tidak)
        if get_user_status(request.user) == "suspended":
            return JsonResponse({
                'success': False,
                'error': 'Akun Anda ditangguhkan. Tidak dapat berkomentar.'
            }, status=403)

        # Ambil isi komentar dari POST, strip untuk menghapus spasi berlebih di awal/akhir
        content = request.POST.get("content", "").strip()
        # Ambil parent_id kalau ini balasan
        parent_id = request.POST.get("parent_id")

        # Jika konten kosong, return error 400
        if not content:
            return JsonResponse({'success': False, 'error': 'Komentar kosong'}, status=400)

        # Jika ada parent_id, ambil objek parent comment; kalau tidak, parent=None
        parent = Comment.objects.filter(id=parent_id).first() if parent_id else None

        # Buat objek Comment baru di database
        comment = Comment.objects.create(
            news=news,
            user=request.user,
            content=content,
            parent=parent
        )

        # Mengirim komentar yang baru dibuat ke Flutter
        # Balas JSON dengan struktur komentar yang sesuai kebutuhan aplikasi Flutter
        return JsonResponse({
            "success": True,
            "comment": {
                "id": comment.id,
                "user": comment.user.username,
                "content": comment.content,
                "created_at": comment.created_at.strftime('%Y-%m-%d %H:%M'),
                "like_count": 0,
                "user_has_liked": False,
                "replies": [],
                "is_owner": True,
            }
        })

    # Jika method GET, berarti client ingin mengambil daftar komentar
    sort = request.GET.get("sort", "latest")

    # Ambil komentar yang terkait dengan berita ini
    comments = Comment.objects.filter(news=news).prefetch_related(
        'likes', 'replies', 'replies__likes', 'replies__replies'
    )

    # Root comments saja
    if sort == "popular":
        comments = comments.filter(parent=None).annotate(
            total_likes=Count("likes")
        ).order_by("-total_likes", "-created_at")
    else:
        comments = comments.filter(parent=None).order_by("-created_at")

    # Fungsi serialize rekursif untuk komentar dan seluruh reply-nya
    def serialize_comment(comment):
        return {
            "id": comment.id,
            "user": comment.user.username,
            "content": comment.content,
            "created_at": comment.created_at.strftime('%Y-%m-%d %H:%M'),
            "like_count": comment.likes.count(),
            # True jika user saat ini sudah like komentar ini; jika tidak login, False
            "user_has_liked": comment.is_liked_by(request.user)
                if request.user.is_authenticated else False,
            # True jika komentar ini milik user yang saat ini login
            "is_owner": request.user == comment.user
                if request.user.is_authenticated else False,
            # Serialize balasan komentar ini, diurutkan terbaru dulu
            "replies": [
                serialize_comment(reply)
                for reply in comment.replies.all().order_by("-created_at")
            ]
        }

    # Menghasilkan list komentar ter-serialize, lalu return sebagai JsonResponse
    return JsonResponse(
        [serialize_comment(c) for c in comments],
        safe=False
    )

# Decorator: hanya mengizinkan method GET
@require_GET
def api_news_recommendations(request, pk):
    # Ambil berita selain berita dengan pk ini, dan urutkan berdasarkan created_at terbaru, ambil 3
    recommended = News.objects.exclude(pk=pk).order_by('-created_at')[:3]
    # Serialisasikan setiap news menjadi dict, lalu return sebagai JSON (list)
    return JsonResponse([serialize_news(n, request) for n in recommended], safe=False)

@csrf_exempt # Nonaktifkan CSRF
@login_required # Hanya user login yang boleh like/unlike
# Endpoint API untuk toggle like komentar
def api_like_comment(request, comment_id):
    # Hanya izinkan method POST
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    # Ambil objek Comment berdasarkan id, atau 404
    comment = get_object_or_404(Comment, id=comment_id)
    # Simpan user saat ini
    user = request.user

    # Cek status user suspended atau tidak
    if get_user_status(request.user) == "suspended":
            return JsonResponse({
                'success': False,
                'error': 'Anda tidak dapat memposting komentar karena akun Anda ditangguhkan'
            }, status=403)

    # Toggle like
    # Jika user sudah ada di likes, hapus (unlike)
    if comment.likes.filter(id=user.id).exists():
        comment.likes.remove(user)
        liked = False
    # Jika belum ada, tambahkan (like)
    else:
        comment.likes.add(user)
        liked = True

    # Return JSON dengan status sukses, liked, dan jumlah like terbaru
    return JsonResponse({
        'success': True,
        'liked': liked,
        'like_count': comment.likes.count(),
    })

@csrf_exempt # Nonaktifkan CSRF
@login_required # User harus login untuk menghapus komentar lewat API
# Endpoint API untuk hapus komentar
def api_delete_comment(request, comment_id):
    # Hanya izinkan method POST
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    # Cari komentar dengan id tertentu yang dimiliki user saat ini
    comment = Comment.objects.filter(id=comment_id, user=request.user).first()

    # Jika tidak ditemukan (mungkin sudah dihapus atau bukan milik user)
    if not comment:
        return JsonResponse({
            "success": False,
            "error": "Komentar tidak ditemukan atau bukan milik Anda"
        }, status=404)

    # Simpan berita terkait sebelum menghapus (untuk menghitung ulang total komentar)
    news = comment.news
    # Hapus komentar
    comment.delete()

    # Hitung total komentar tersisa pada berita tersebut
    total_comments = Comment.objects.filter(news=news).count()

    # Return JSON sukses dengan pesan dan total_comments terbaru
    return JsonResponse({
        "success": True,
        "message": "Komentar berhasil dihapus",
        "total_comments": total_comments
    })

@csrf_exempt # Nonaktifkan CSRF
# Endpoint API untuk mengembalikan data singkat user saat ini
def api_current_user(request):
    # Jika user belum login, kembalikan info bahwa user tidak terautentikasi
    if not request.user.is_authenticated:
        return JsonResponse({
            "authenticated": False,
            "role": "anonymous",
            "status": "anonymous",
        })

    # Jika user sudah login, kirim data username, role, dan status hasil get_user_status()
    return JsonResponse({
        "authenticated": True,
        "username": request.user.username,
        "role": request.user.role,
        "status": get_user_status(request.user),
    })

@csrf_exempt # Nonaktifkan CSRF
# Endpoint API untuk membuat berita baru dengan payload JSON (bukan form)
def api_news_create_json(request):
    # Hanya izinkan method POST, method lain dianggap tidak diperbolehkan
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        # Parse body request (bytes) menjadi dict Python menggunakan json.loads()
        data = json.loads(request.body)

        # Ambil field-field dari JSON (title, content, category, is_featured, thumbnail_base64)
        title = data.get("title")
        content = data.get("content")
        category = data.get("category")
        is_featured = data.get("is_featured", False)
        thumb_base64 = data.get("thumbnail_base64")

        # Buat instance News tetapi belum disimpan
        news = News(
            title=title,
            content=content,
            category=category,
            is_featured=is_featured,
            author=request.user
        )

        # Handle base64 image
        if thumb_base64:
            img_data = base64.b64decode(thumb_base64)
            news.thumbnail = ContentFile(img_data, "thumb.jpg")

        # Simpan objek News ke database
        news.save()
        # Kembalikan JSON dengan status success dan id berita yang baru dibuat
        return JsonResponse({"status": "success", "id": news.id}, status=201)

    # Jika ada error, catch exception dan kembalikan status error
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
    
@csrf_exempt # Nonaktifkan CSRF
# Endpoint API untuk mengedit berita via JSON payload
def api_news_edit_json(request, pk):
    # Hanya izinkan POST (bisa dianggap sebagai "update" di sini)
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    # Ambil objek News, 404 jika tidak ada
    news = get_object_or_404(News, pk=pk)
    # Cek apakah user yang login adalah author
    is_owner = news.author == request.user

    try:
        # Parse body JSON menjadi dict
        data = json.loads(request.body)

        # Update field-field News jika key tersedia di JSON; jika tidak, pakai nilai lama
        news.title = data.get("title", news.title)
        news.content = data.get("content", news.content)
        news.category = data.get("category", news.category)
        news.is_featured = data.get("is_featured", False)
        # Update waktu edited_at ke datetime sekarang
        news.edited_at = datetime.now()

        # Handle penghapusan thumbnail
        if data.get("delete_thumbnail") is True:
            if news.thumbnail:
                news.thumbnail.delete(save=False)
                news.thumbnail = None

        # Handle penggantian thumbnail
        thumb_base64 = data.get("thumbnail_base64")
        if thumb_base64:
            img_data = base64.b64decode(thumb_base64)
            news.thumbnail = ContentFile(img_data, "thumb.jpg")

        # Simpan perubahan ke database
        news.save()

        # Return JSON sukses
        return JsonResponse({"status": "success", "id": news.id})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@csrf_exempt # Nonaktifkan CSRF
def api_news_delete(request, pk):
    # Hanya izinkan method POST untuk delete di endpoint ini
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=405)

    # Ambil News atau 404 jika tidak ada
    news = get_object_or_404(News, pk=pk)
    # Cek apakah user saat ini adalah author berita
    is_owner = news.author == request.user
    # Jika bukan pemilik, balas status 403 Unauthorized
    if not is_owner:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)
    # Jika pemilik, hapus berita
    news.delete()
    # Balas JSON bahwa penghapusan berhasil
    return JsonResponse({
        "status": "success",
        "message": "Berita berhasil dihapus"
    })