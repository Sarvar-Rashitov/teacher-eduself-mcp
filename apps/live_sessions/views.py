# apps/live_sessions/views.py
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.permissions import IsTeacher
from apps.quizzes.models import Quiz
from .models import LiveSession
from .serializers import (
    LiveSessionSerializer,
    ParticipantSerializer,
    JoinSessionSerializer
)
from .services import SessionService


class CreateSessionView(APIView):
    """
    O'qituvchi yangi jonli sessiya ochishi (POST /api/sessions/).
    """
    permission_classes = [IsAuthenticated, IsTeacher]

    def post(self, request):
        quiz_id = request.data.get('quiz_id')
        game_mode = request.data.get('game_mode', 'classic')

        if not quiz_id:
            return Response(
                {'error': "quiz_id maydoni majburiy."},
                status=status.HTTP_400_BAD_REQUEST
            )

        quiz = Quiz.objects.filter(id=quiz_id, owner=request.user).first()
        if not quiz:
            return Response(
                {'error': "Quiz topilmadi yoki sizga tegishli emas."},
                status=status.HTTP_404_NOT_FOUND
            )

        if quiz.questions.count() == 0:
            return Response(
                {'error': "Bo'sh quiz bo'yicha jonli sessiya ochib bo'lmaydi. Kamida 1 ta savol qo'shing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        session = SessionService.create_session(
            quiz=quiz,
            host=request.user,
            game_mode=game_mode,
            settings_payload=request.data.get('settings', {})
        )

        return Response(
            LiveSessionSerializer(session).data,
            status=status.HTTP_201_CREATED
        )


class JoinSessionView(APIView):
    """
    O'quvchi PIN kod va ism orqali xonaga qo'shilishi (POST /api/sessions/join/).
    REALTIME_PROTOCOL.md §2 talabi.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = JoinSessionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        room_code = serializer.validated_data['room_code']
        nickname = serializer.validated_data['nickname']

        try:
            participant, session, token = SessionService.join_session(room_code, nickname)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status': 'ok',
            'session_id': str(session.id),
            'room_code': session.room_code,
            'participant_id': str(participant.id),
            'nickname': participant.nickname,
            'anonymous_token': token,
            'role': 'student',
            'ws_url': f"/ws/session/{session.room_code}/?token={token}"
        }, status=status.HTTP_200_OK)


class SessionDetailView(APIView):
    """
    Sessiya ma'lumotlarini olish (GET /api/sessions/<room_code>/).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, room_code):
        session = LiveSession.objects.filter(room_code=room_code).first()
        if not session:
            return Response({'error': 'Sessiya topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        participants = session.participants.all()
        return Response({
            'session': LiveSessionSerializer(session).data,
            'participants': ParticipantSerializer(participants, many=True).data
        })
