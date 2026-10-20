# core/views_ui.py
"""
Django MVT Views for EduSelf Teacher & EduPlay 3D frontend interface.
Four Core Experiences:
1. Teacher Dashboard & Auth (/dashboard/, /login/, /profile/)
2. Universal Quiz Editor (/editor/new/, /editor/<uuid>/)
3. Live Host Big Screen (/live/<room_code>/, /live/launch/<uuid>/)
4. Student Mobile Play Interface (/play/, /play/<room_code>/)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.live_sessions.services import RoomCodeGenerator


def index_view(request):
    """Bosh sahifa: agar tizimga kirilgan bo'lsa dashboard, aks holda login."""
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    return redirect('/login/')


from apps.authentication.security import BruteForceProtector


def login_view(request):
    """O'qituvchi kirish sahifasi (Brute-force himoyasi bilan)."""
    if request.user.is_authenticated:
        return redirect('/dashboard/')

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    client_ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR', '127.0.0.1')

    is_locked, remaining_seconds = BruteForceProtector.is_locked(client_ip)
    if is_locked:
        return render(request, 'auth/login.html', {
            'error': f"Ko'p xato urinishlar tufayli hisobingiz vaqtincha bloklandi. Iltimos, {remaining_seconds} soniyadan so'ng qayta urinib ko'ring."
        }, status=429)

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            BruteForceProtector.reset_attempts(client_ip)
            login(request, user)
            next_url = request.GET.get('next') or '/dashboard/'
            return redirect(next_url)

        attempts, is_now_locked = BruteForceProtector.record_failed_attempt(client_ip)
        if is_now_locked:
            return render(request, 'auth/login.html', {
                'error': "5 marta xato parol kiritildi. Hisobingiz 15 daqiqaga bloklandi."
            }, status=429)

        remaining_attempts = max(0, BruteForceProtector.MAX_ATTEMPTS - attempts)
        return render(request, 'auth/login.html', {
            'error': f"Foydalanuvchi nomi yoki maxfiy parol noto'g'ri. (Qolgan urinishlar: {remaining_attempts})"
        })

    return render(request, 'auth/login.html')


def logout_view(request):
    """Tizimdan chiqish."""
    logout(request)
    return redirect('/login/')


@login_required(login_url='/login/')
def profile_view(request):
    """O'qituvchi profili, obuna rejasi va AI limitlari."""
    return render(request, 'auth/profile.html', {'user': request.user})


@login_required(login_url='/login/')
def dashboard_view(request):
    """Bento Grid Teacher Dashboard: viktorinalar ro'yxati va tezkor statistika."""
    quizzes = Quiz.objects.filter(owner=request.user).order_by('-created_at')
    active_sessions_count = LiveSession.objects.filter(
        host=request.user,
        status__in=['lobby', 'in_progress']
    ).count()

    stats = {
        'avg_accuracy': 84,
        'total_quizzes': quizzes.count(),
        'active_sessions': active_sessions_count,
    }
    return render(request, 'dashboard/teacher_home.html', {
        'quizzes': quizzes,
        'stats': stats
    })


@login_required(login_url='/login/')
def quiz_editor_view(request, quiz_id=None):
    """3 ustunli universal viktorina muharriri (WYSIWYG preview & AI Drawer)."""
    quiz = None
    if quiz_id:
        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)
    return render(request, 'editor/quiz_editor.html', {'quiz': quiz})


def host_screen_view(request, room_code):
    """Sinf proyektori / Katta ekran: Ulkan PIN, 30s radial taymer va 3D shohsupa."""
    session = LiveSession.objects.filter(room_code=room_code).first()
    return render(request, 'live/host_screen.html', {
        'room_code': room_code,
        'session': session
    })


@login_required(login_url='/login/')
def launch_live_view(request, quiz_id):
    """Viktorinani jonli sessiya sifatida ishga tushirish va proyektor ekraniga yo'naltirish."""
    quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)
    code = RoomCodeGenerator.generate_unique_code()
    session = LiveSession.objects.create(
        quiz=quiz,
        host=request.user,
        room_code=code,
        status='lobby'
    )
    return redirect(f'/live/{code}/')


def student_game_view(request, room_code=None):
    """Talabalar smartfoni uchun dual-coded o'yin maydoni (▲, ◆, ●, ■)."""
    return render(request, 'player/student_game.html', {
        'room_code': room_code or ''
    })
