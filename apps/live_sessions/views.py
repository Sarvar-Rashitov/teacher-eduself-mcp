from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from apps.authentication.permissions import IsTeacher
from apps.quizzes.models import Quiz
from .models import LiveSession, Participant
from .services import LiveSessionService
from .fsm import SessionStateMachine


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTeacher])
def session_create_view(request):
    """
    O'qituvchi tomonidan yangi jonli sessiya ochish.
    6 xonali unikal PIN yaratiladi va xona LOBBY holatiga o'tadi.
    """
    quiz_id = request.data.get("quiz_id")
    if not quiz_id:
        return Response({"error": "quiz_id ko'rsatilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

    quiz = get_object_or_404(Quiz, pk=quiz_id, owner=request.user)
    game_mode = request.data.get("game_mode", "classic")
    settings_payload = request.data.get("settings", {})

    session = LiveSessionService.create_session(
        host=request.user,
        quiz=quiz,
        game_mode=game_mode,
        settings_payload=settings_payload,
    )

    return Response({
        "session_id": str(session.id),
        "room_code": session.room_code,
        "status": session.status,
        "quiz_title": quiz.title,
        "game_mode": session.game_mode,
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([AllowAny])
def session_join_view(request):
    """
    O'quvchi xonaga PIN kod va taxallus bilan qo'shilishi (1-bosqich Handshake).
    """
    room_code = request.data.get("room_code") or request.data.get("pin")
    nickname = request.data.get("nickname")

    if not room_code or not nickname:
        return Response(
            {"error": "Xona PIN kodi va taxallus (nickname) kiritilishi shart"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        participant, session = LiveSessionService.join_session(room_code=room_code, nickname=nickname)
        questions = []
        if session.quiz:
            for q in session.quiz.questions.all().order_by("order_index"):
                questions.append({
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

        return Response({
            "status": "ok",
            "session_id": str(session.id),
            "room_code": session.room_code,
            "quiz_title": session.quiz.title if session.quiz else "",
            "participant_id": str(participant.id),
            "nickname": participant.nickname,
            "anonymous_token": participant.anonymous_token,
            "session_status": session.status,
            "questions": questions,
        }, status=status.HTTP_200_OK)
    except ValidationError as exc:
        return Response({"error": str(exc.message if hasattr(exc, "message") else exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def session_reconnect_view(request):
    """
    Internet uzilib qolgan o'quvchining sessiyasini tiklash (Reconnection).
    """
    token = request.data.get("anonymous_token") or request.data.get("token")
    if not token:
        return Response({"error": "anonymous_token kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)

    participant = LiveSessionService.reconnect_participant(token)
    if not participant:
        return Response(
            {"error": "Ulanish ma'lumotlari topilmadi yoki sessiya tugagan"},
            status=status.HTTP_404_NOT_FOUND
        )

    session = participant.session
    return Response({
        "status": "reconnected",
        "session_id": str(session.id),
        "room_code": session.room_code,
        "participant_id": str(participant.id),
        "nickname": participant.nickname,
        "score": participant.score,
        "streak": participant.streak,
        "session_status": session.status,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([AllowAny])
def session_state_view(request, room_code):
    """
    Xona holati va ulangan ishtirokchilar sonini olish.
    """
    session = get_object_or_404(LiveSession, room_code=room_code)
    participants = session.participants.all()

    return Response({
        "session_id": str(session.id),
        "room_code": session.room_code,
        "status": session.status,
        "is_locked": session.is_locked,
        "quiz_title": session.quiz.title,
        "total_participants": participants.count(),
        "participants": [
            {
                "id": str(p.id),
                "nickname": p.nickname,
                "score": p.score,
                "is_connected": p.is_connected,
            }
            for p in participants
        ],
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def session_start_view(request, room_code):
    """
    Host o'yinni boshlashi (LOBBY -> ACTIVE holatiga o'tkazish).
    """
    session = get_object_or_404(LiveSession, room_code=room_code)
    try:
        SessionStateMachine.start_game(session)
    except Exception:
        session.status = SessionState.ACTIVE
        session.save(update_fields=["status"])

    return Response({
        "status": "ok",
        "room_code": room_code,
        "session_status": session.status,
    }, status=status.HTTP_200_OK)
