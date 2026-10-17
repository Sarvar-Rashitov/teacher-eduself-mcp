"""
REST API Views for Live Sessions.
Supports session creation by teachers, student join/reconnect handshake, and state snapshots.
"""

from rest_framework import status, views, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.authentication.permissions import IsTeacher
from apps.quizzes.models import Quiz
from .models import LiveSession, Participant
from .services import LiveSessionService, ReconnectionManager, SessionJoinError, SessionLockedError
from .serializers import (
    CreateSessionSerializer,
    JoinSessionSerializer,
    LiveSessionSerializer,
    ParticipantSerializer
)


class CreateSessionView(views.APIView):
    """
    O'qituvchi tomonidan yangi jonli sessiya (xona) ochish.
    POST /api/v1/sessions/create/
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacher]

    def post(self, request):
        serializer = CreateSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quiz = Quiz.objects.get(id=serializer.validated_data['quiz_id'])
        game_mode = serializer.validated_data.get('game_mode', 'classic')
        settings_payload = serializer.validated_data.get('settings_payload', {})

        session = LiveSessionService.create_session(
            quiz=quiz,
            host=request.user,
            game_mode=game_mode,
            settings_payload=settings_payload
        )

        host_ticket = ReconnectionManager.generate_ticket(
            session_id=session.id,
            role='host'
        )

        return Response({
            'status': 'ok',
            'session': LiveSessionSerializer(session).data,
            'host_ticket': host_ticket,
            'join_url': f"/join/{session.room_code}"
        }, status=status.HTTP_201_CREATED)


class JoinSessionView(views.APIView):
    """
    O'quvchi tomonidan PIN kod va taxallus bilan sessiyaga ulanish.
    POST /api/v1/sessions/join/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = JoinSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room_code = serializer.validated_data['room_code'].strip()
        nickname = serializer.validated_data['nickname'].strip()
        team_name = serializer.validated_data.get('team_name')
        anon_token = serializer.validated_data.get('anonymous_token')

        try:
            participant, session, ticket = LiveSessionService.join_session(
                room_code=room_code,
                nickname=nickname,
                team_name=team_name,
                anonymous_token=anon_token
            )
        except SessionLockedError as e:
            return Response({'error': str(e), 'code': 'ROOM_LOCKED'}, status=status.HTTP_403_FORBIDDEN)
        except SessionJoinError as e:
            return Response({'error': str(e), 'code': 'JOIN_REJECTED'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status': 'ok',
            'ticket': ticket,
            'session_id': str(session.id),
            'room_code': session.room_code,
            'participant_id': str(participant.id),
            'anonymous_token': participant.anonymous_token,
            'nickname': participant.nickname,
            'team_name': participant.team_name,
        }, status=status.HTTP_200_OK)


class SessionStateView(views.APIView):
    """
    Sessiyaning joriy holat snapshotini olish.
    GET /api/v1/sessions/<room_code>/state/
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, room_code):
        session = get_object_or_404(LiveSession, room_code=room_code)
        is_host = request.user.is_authenticated and session.host == request.user

        anon_token = request.headers.get('X-Participant-Token') or request.query_params.get('token')
        participant = None
        if anon_token:
            participant = Participant.objects.filter(session=session, anonymous_token=anon_token).first()

        snapshot = LiveSessionService.get_state_snapshot(
            session=session,
            participant=participant,
            is_host=is_host
        )
        return Response(snapshot, status=status.HTTP_200_OK)


class SessionDetailView(views.APIView):
    """
    Sessiya umumiy ma'lumotlari.
    GET /api/v1/sessions/<room_code>/
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, room_code):
        session = get_object_or_404(LiveSession, room_code=room_code)
        return Response(LiveSessionSerializer(session).data, status=status.HTTP_200_OK)
