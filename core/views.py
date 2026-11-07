"""
Frontend MVT views for EduSelf Teacher — "EduPlay 3D" (Phase 08).
"""

import json
from django.db import models
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession


def ensure_default_quizzes(user=None):
    """
    O'qituvchi boshqaruv panelida 'kasr' viktorinasi (va boshqa standart viktorinalar)
    doimiy saqlanib turishini ta'minlovchi kafolatlangan generator.
    """
    from apps.authentication.models import User

    target_user = user
    if not target_user or not getattr(target_user, "is_authenticated", False):
        target_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(role="teacher").first()
    if not target_user:
        return

    kasr_quiz = Quiz.objects.filter(title="kasr").first()
    if not kasr_quiz:
        kasr_quiz = Quiz.objects.create(
            owner=target_user,
            title="kasr",
            subject="matematika",
            grade_level=9,
            status="draft",
            description="Matematika fanidan kasrlar va sonli hisoblashlar bo‘yicha interaktiv viktorina",
            current_version=1,
        )

    if kasr_quiz.questions.count() == 0:
        sample_questions = [
            {
                "order_index": 0,
                "prompt": "Kasrni eng sodda (qisqarmas) ko‘rinishga keltiring: 24/36",
                "options": [
                    {"id": "opt_1", "text": "2/3"},
                    {"id": "opt_2", "text": "3/4"},
                    {"id": "opt_3", "text": "4/5"},
                    {"id": "opt_4", "text": "1/2"},
                ],
                "correct_answer": "opt_1",
                "points": 1000,
                "time_limit_seconds": 30,
            },
            {
                "order_index": 1,
                "prompt": "Hisoblang: 1/4 + 2/4",
                "options": [
                    {"id": "opt_1", "text": "3/4"},
                    {"id": "opt_2", "text": "3/8"},
                    {"id": "opt_3", "text": "2/8"},
                    {"id": "opt_4", "text": "1"},
                ],
                "correct_answer": "opt_1",
                "points": 1000,
                "time_limit_seconds": 30,
            },
            {
                "order_index": 2,
                "prompt": "Hisoblang: 5/6 - 1/3",
                "options": [
                    {"id": "opt_1", "text": "1/2"},
                    {"id": "opt_2", "text": "4/3"},
                    {"id": "opt_3", "text": "2/3"},
                    {"id": "opt_4", "text": "1/3"},
                ],
                "correct_answer": "opt_1",
                "points": 1000,
                "time_limit_seconds": 30,
            },
            {
                "order_index": 3,
                "prompt": "Hisoblang: 2/3 * 3/4",
                "options": [
                    {"id": "opt_1", "text": "1/2"},
                    {"id": "opt_2", "text": "5/7"},
                    {"id": "opt_3", "text": "6/7"},
                    {"id": "opt_4", "text": "2/4"},
                ],
                "correct_answer": "opt_1",
                "points": 1000,
                "time_limit_seconds": 30,
            },
            {
                "order_index": 4,
                "prompt": "Hisoblang: 3/4 : 1/2",
                "options": [
                    {"id": "opt_1", "text": "3/2"},
                    {"id": "opt_2", "text": "3/8"},
                    {"id": "opt_3", "text": "1/2"},
                    {"id": "opt_4", "text": "2/3"},
                ],
                "correct_answer": "opt_1",
                "points": 1000,
                "time_limit_seconds": 30,
            },
        ]
        for q_data in sample_questions:
            Question.objects.create(quiz=kasr_quiz, **q_data)


def home_view(request):
    """Bosh sahifaga kirganda foydalanuvchini dashboard yoki login sahifasiga yo'naltirish."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("/auth/login/")


@login_required(login_url="/auth/login/")
def dashboard_view(request):
    """O'qituvchining asosiy Bento Grid boshqaruv paneli."""
    ensure_default_quizzes(request.user)
    if request.user.is_superuser or request.user.is_staff:
        quizzes = Quiz.objects.all().order_by("-created_at")
    else:
        quizzes = Quiz.objects.filter(
            models.Q(owner=request.user) | models.Q(title="kasr") | models.Q(owner__is_superuser=True)
        ).distinct().order_by("-created_at")
    return render(request, "dashboard/teacher_home.html", {"quizzes": quizzes})


@login_required(login_url="/auth/login/")
def quiz_editor_view(request, quiz_id=None):
    """Savollar muharriri va AI yordamchi paneli."""
    quiz = None
    questions_data = []
    if quiz_id:
        if request.user.is_superuser or request.user.is_staff:
            quiz = get_object_or_404(Quiz, id=quiz_id)
        else:
            quiz = Quiz.objects.filter(
                models.Q(id=quiz_id) & (models.Q(owner=request.user) | models.Q(title="kasr") | models.Q(owner__is_superuser=True))
            ).first()
            if not quiz:
                quiz = get_object_or_404(Quiz, id=quiz_id)

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

    participants = list(session.participants.all().order_by("-score", "joined_at")) if session else []
    participants_payload = []
    if session:
        for p in participants:
            c_count = p.correct_answers_count
            i_count = p.incorrect_answers_count
            if c_count == 0 and i_count == 0:
                c_count = session.submissions.filter(participant=p, is_correct=True).count()
                i_count = session.submissions.filter(participant=p, is_correct=False).count()
            participants_payload.append({
                "id": str(p.id),
                "nickname": p.nickname,
                "avatar": p.team_name or "fa-solid fa-dog",
                "score": p.score,
                "correct_answers": c_count,
                "incorrect_answers": i_count,
            })

    return render(request, "live/host_screen.html", {
        "room_code": room_code,
        "session": session,
        "quiz": quiz,
        "participants": participants,
        "participants_count": len(participants),
        "participants_json": json.dumps(participants_payload, ensure_ascii=False),
        "questions_json": json.dumps(questions_data, ensure_ascii=False),
    })


def student_game_view(request, room_code=""):
    """O'quvchi mobil ekrani (Dual-coded 4 ta rang/shakl)."""
    session = LiveSession.objects.filter(room_code=room_code).first() if room_code else None
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


def robots_txt(request):
    """Qidiruv tizimlari (Google, Yandex) uchun robots.txt fayli."""
    domain = request.build_absolute_uri('/')[:-1]
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /play/",
        "Allow: /auth/login/",
        "Allow: /auth/register/",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /mcp/",
        "Disallow: /health/",
        "",
        f"Sitemap: {domain}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    """Qidiruv tizimlari botlari uchun dinamik sitemap.xml xaritasi."""
    domain = request.build_absolute_uri('/')[:-1]
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{domain}/</loc>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>{domain}/play/</loc>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>{domain}/auth/login/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>{domain}/auth/register/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>"""
    return HttpResponse(xml_content.strip(), content_type="application/xml")
