"""
Frontend MVT views for EduSelf Teacher — "EduPlay 3D" (Phase 08).
"""

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession


def home_view(request):
    """Bosh sahifaga kirganda foydalanuvchini dashboard yoki login sahifasiga yo'naltirish."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("/auth/login/")


@login_required(login_url="/auth/login/")
def dashboard_view(request):
    """O'qituvchining asosiy Bento Grid boshqaruv paneli."""
    quizzes = Quiz.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "dashboard/teacher_home.html", {"quizzes": quizzes})


@login_required(login_url="/auth/login/")
def quiz_editor_view(request, quiz_id=None):
    """Savollar muharriri va AI yordamchi paneli."""
    quiz = None
    questions_data = []
    if quiz_id:
        quiz = get_object_or_404(Quiz, id=quiz_id, owner=request.user)
        for q in quiz.questions.all().order_by("order_index"):
            questions_data.append({
                "id": str(q.id),
                "type": q.type,
                "prompt": q.prompt,
                "media_url": q.media_url,
                "media_type": q.media_type,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "time_limit_seconds": q.time_limit_seconds,
                "points": q.points,
                "is_locked": q.is_locked,
            })
    return render(request, "editor/quiz_editor.html", {
        "quiz": quiz,
        "questions_json": json.dumps(questions_data, ensure_ascii=False),
    })


def host_screen_view(request, room_code):
    """Sinf proyektori uchun katta ekran (Shohsupa, PIN kod, animatsiyalar)."""
    session = LiveSession.objects.filter(room_code=room_code).first()
    quiz = session.quiz if session else None
    questions_data = []
    if quiz:
        for q in quiz.questions.all().order_by("order_index"):
            questions_data.append({
                "id": str(q.id),
                "order": q.order_index,
                "prompt": q.prompt,
                "media_url": q.media_url,
                "media_type": q.media_type,
                "type": q.type,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "time_limit_seconds": q.time_limit_seconds,
                "points": q.points,
            })
    return render(request, "live/host_screen.html", {
        "room_code": room_code,
        "session": session,
        "quiz": quiz,
        "questions_json": json.dumps(questions_data, ensure_ascii=False),
    })


def student_game_view(request, room_code=""):
    """O'quvchi mobil ekrani (Dual-coded 4 ta rang/shakl)."""
    session = LiveSession.objects.filter(room_code=room_code).first() if room_code else None
    quiz = session.quiz if session else None
    if not quiz:
        quiz = Quiz.objects.filter(questions__isnull=False).distinct().order_by("-created_at").first()

    questions_data = []
    if quiz:
        for q in quiz.questions.all().order_by("order_index"):
            questions_data.append({
                "id": str(q.id),
                "order": q.order_index,
                "prompt": q.prompt,
                "media_url": q.media_url,
                "media_type": q.media_type,
                "type": q.type,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "time_limit_seconds": q.time_limit_seconds,
                "points": q.points,
            })
    return render(request, "player/student_game.html", {
        "room_code": room_code,
        "session": session,
        "quiz": quiz,
        "questions_json": json.dumps(questions_data, ensure_ascii=False),
    })


@login_required(login_url="/auth/login/")
def profile_view(request):
    """O'qituvchi profili sahifasi."""
    success_msg = None
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip()
        if first_name is not None:
            request.user.first_name = first_name
        if last_name is not None:
            request.user.last_name = last_name
        if email:
            request.user.email = email
        request.user.save()
        success_msg = "Profil ma'lumotlari muvaffaqiyatli saqlandi! ✅"

    return render(request, "auth/profile.html", {
        "user": request.user,
        "success_msg": success_msg,
    })
