from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.authentication.permissions import IsTeacher
from .models import Quiz, Question, QuizVersion
from .serializers import (
    QuizSerializer,
    QuizDetailSerializer,
    TeacherQuestionSerializer,
    StudentQuestionSerializer,
    QuizVersionSerializer,
)
from .services import QuizCRUDService, VersionManager, QuestionValidator
from apps.questions_registry.exceptions import QuestionValidationError


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsTeacher])
def quiz_list_create_view(request):
    """
    O'qituvchining viktorinalar ro'yxatini olish (GET) yoki yangi yaratish (POST).
    """
    if request.method == "GET":
        quizzes = Quiz.objects.filter(owner=request.user).prefetch_related("questions")
        serializer = QuizSerializer(quizzes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        data = request.data
        try:
            quiz = QuizCRUDService.create_quiz(
                owner=request.user,
                title=data.get("title", ""),
                subject=data.get("subject", ""),
                grade_level=data.get("grade_level", 7),
                locale=data.get("locale", "uz-Latn"),
                description=data.get("description", ""),
            )
            return Response(QuizDetailSerializer(quiz).data, status=status.HTTP_201_CREATED)
        except QuestionValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsTeacher])
def quiz_detail_view(request, pk):
    """
    Viktorina tafsilotlarini ko'rish, yangilash yoki o'chirish.
    """
    quiz = get_object_or_404(Quiz, pk=pk, owner=request.user)

    if request.method == "GET":
        return Response(QuizDetailSerializer(quiz).data, status=status.HTTP_200_OK)

    elif request.method in ("PUT", "PATCH"):
        serializer = QuizSerializer(quiz, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        quiz.delete()
        return Response({"status": "ok", "message": "Viktorina o'chirildi"}, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTeacher])
def quiz_add_question_view(request, pk):
    """
    Viktorinaga yangi savol qo'shish.
    """
    quiz = get_object_or_404(Quiz, pk=pk, owner=request.user)
    try:
        question = QuizCRUDService.add_question(quiz, request.data)
        return Response(TeacherQuestionSerializer(question).data, status=status.HTTP_201_CREATED)
    except QuestionValidationError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsTeacher])
def question_detail_view(request, quiz_pk, question_pk):
    """
    Muayyan savolni yangilash yoki o'chirish.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_pk, owner=request.user)
    question = get_object_or_404(Question, pk=question_pk, quiz=quiz)

    if request.method in ("PUT", "PATCH"):
        try:
            force = request.data.get("force", False)
            updated_question = QuizCRUDService.update_question(question, request.data, force=force)
            return Response(TeacherQuestionSerializer(updated_question).data, status=status.HTTP_200_OK)
        except QuestionValidationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        if question.is_locked:
            return Response(
                {"error": "Qulflangan savolni o'chirib bo'lmaydi"},
                status=status.HTTP_400_BAD_REQUEST
            )
        question.delete()
        return Response({"status": "ok", "message": "Savol o'chirildi"}, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTeacher])
def quiz_snapshot_view(request, pk):
    """
    Viktorinaning joriy holatini muzlatish (Snapshot / Yangi versiya yaratish).
    """
    quiz = get_object_or_404(Quiz, pk=pk, owner=request.user)
    version = VersionManager.create_snapshot(quiz)
    return Response(QuizVersionSerializer(version).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsTeacher])
def quiz_version_list_view(request, pk):
    """
    Viktorina versiyalari tarixini olish.
    """
    quiz = get_object_or_404(Quiz, pk=pk, owner=request.user)
    versions = quiz.versions.all()
    return Response(QuizVersionSerializer(versions, many=True).data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def quiz_student_preview_view(request, pk):
    """
    Zero-Knowledge Talaba ko'rinishi (To'g'ri javob kalitlarisiz savollar).
    """
    quiz = get_object_or_404(Quiz, pk=pk)
    questions = quiz.questions.all().order_by("order_index")
    serializer = StudentQuestionSerializer(questions, many=True)
    return Response({
        "quiz_id": str(quiz.id),
        "title": quiz.title,
        "subject": quiz.subject,
        "questions": serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTeacher])
def upload_question_image_view(request):
    """
    Savol uchun rasm yuklash (JPEG, PNG, WebP, GIF, SVG).
    Media papkasiga saqlanadi va URL qaytariladi.
    """
    import os
    import uuid
    from django.conf import settings

    image_file = request.FILES.get("image")
    if not image_file:
        return Response({"error": "Rasm fayli ('image') tanlanmagan."}, status=status.HTTP_400_BAD_REQUEST)

    # Hajmni tekshirish (maksimum 10MB)
    if image_file.size > 10 * 1024 * 1024:
        return Response({"error": "Rasm hajmi 10 MB dan oshmasligi kerak."}, status=status.HTTP_400_BAD_REQUEST)

    ext = os.path.splitext(image_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
        return Response({"error": "Faqat JPG, PNG, WebP, GIF yoki SVG formatidagi rasmlar qabul qilinadi."}, status=status.HTTP_400_BAD_REQUEST)

    save_dir = os.path.join(settings.MEDIA_ROOT, "question_images")
    os.makedirs(save_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(save_dir, unique_filename)

    with open(dest_path, "wb+") as dest:
        for chunk in image_file.chunks():
            dest.write(chunk)

    media_url = f"{settings.MEDIA_URL}question_images/{unique_filename}"
    return Response({
        "status": "ok",
        "url": media_url,
        "filename": unique_filename,
    }, status=status.HTTP_201_CREATED)
