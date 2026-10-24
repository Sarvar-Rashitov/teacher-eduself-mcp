from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404

from quizzes.models import Quiz
from .models import LiveSession, Participant
from .serializers import (
    LiveSessionSerializer,
    LiveSessionCreateSerializer,
    JoinSessionSerializer,
    ParticipantSerializer,
)
from .services import LiveSessionService
from .fsm import SessionStateMachine


class LiveSessionViewSet(viewsets.ModelViewSet):
    """
    Host REST API for managing Live Classroom Sessions.
    """

    queryset = LiveSession.objects.all()
    serializer_class = LiveSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return LiveSession.objects.filter(host=user)
        return LiveSession.objects.none()

    def create(self, request, *args, **kwargs):
        serializer = LiveSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quiz_id = serializer.validated_data["quiz_id"]
        quiz = get_object_or_404(Quiz, id=quiz_id)

        if quiz.owner != request.user and not request.user.is_staff:
            raise PermissionDenied("Siz ushbu viktorinaga ega emassiz.")

        session = LiveSessionService.create_session(
            host=request.user,
            quiz=quiz,
            game_mode=serializer.validated_data.get("game_mode", "classic"),
            settings_payload=serializer.validated_data.get("settings_payload", {})
        )

        return Response(LiveSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        session = self.get_object()
        SessionStateMachine.start_game(session)
        return Response(LiveSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        session = self.get_object()
        SessionStateMachine.pause(session)
        return Response(LiveSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        session = self.get_object()
        SessionStateMachine.resume(session)
        return Response(LiveSessionSerializer(session).data)

    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        session = self.get_object()
        SessionStateMachine.end_game(session)
        return Response(LiveSessionSerializer(session).data)


class JoinSessionAPIView(APIView):
    """
    Two-stage handshake Step 1 (HTTP REST):
    Student submits 6-digit room PIN and nickname to obtain a 60s single-use Ticket
    for upgrading to WebSocket (DOC-58 Section 2).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = JoinSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        room_code = serializer.validated_data["room_code"]
        nickname = serializer.validated_data["nickname"]
        anon_token = serializer.validated_data.get("anonymous_token")

        try:
            participant, ticket, is_reconnection = LiveSessionService.join_session(
                room_code=room_code,
                nickname=nickname,
                anonymous_token=anon_token,
                user=request.user
            )

            return Response({
                "ticket": ticket,
                "session_id": str(participant.session.id),
                "participant_id": str(participant.id),
                "anonymous_token": participant.anonymous_token,
                "room_code": participant.session.room_code,
                "role": "student",
                "is_reconnection": is_reconnection,
            }, status=status.HTTP_200_OK)

        except ValidationError as exc:
            return Response({"error": exc.message if hasattr(exc, "message") else str(exc)}, status=status.HTTP_400_BAD_REQUEST)
