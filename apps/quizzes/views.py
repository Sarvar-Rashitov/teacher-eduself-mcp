from django.db.models import Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import Quiz, Question, QuizVersion
from .serializers import (
    QuizSerializer,
    QuizStudentSerializer,
    QuizCreateUpdateSerializer,
    QuestionSerializer,
    QuestionStudentSerializer,
    QuestionCreateUpdateSerializer,
    QuizVersionSerializer,
)
from .services import QuizCRUD, VersionManager


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow owners of a quiz to edit it."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        quiz = obj if isinstance(obj, Quiz) else getattr(obj, "quiz", None)
        return quiz and (quiz.owner == request.user or request.user.is_staff)


class QuizViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Quizzes.
    Provides teacher CRUD, Zero-Knowledge student views, version snapshots,
    and question reordering.
    """

    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if self.action == "student_view":
            return Quiz.objects.all()
        if user.is_authenticated:
            return Quiz.objects.filter(Q(owner=user) | Q(is_public=True)).distinct()
        return Quiz.objects.filter(is_public=True, status="published")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return QuizCreateUpdateSerializer
        if self.action == "student_view":
            return QuizStudentSerializer
        return QuizSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["get"], permission_classes=[permissions.AllowAny])
    def student_view(self, request, pk=None):
        """
        Returns Zero-Knowledge sanitized representation for student / projector clients.
        """
        quiz = self.get_object()
        serializer = QuizStudentSerializer(quiz)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """
        Publishes the quiz and creates an immutable version snapshot.
        """
        quiz = self.get_object()
        self.check_object_permissions(request, quiz)
        try:
            published_quiz = QuizCRUD.publish_quiz(quiz, user=request.user)
            return Response(QuizSerializer(published_quiz).data)
        except Exception as exc:
            raise ValidationError(str(exc))

    @action(detail=True, methods=["get"])
    def versions(self, request, pk=None):
        """
        Returns the version snapshot history of this quiz.
        """
        quiz = self.get_object()
        self.check_object_permissions(request, quiz)
        versions = quiz.versions.all().order_by("-version_number")
        serializer = QuizVersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def create_version(self, request, pk=None):
        """
        Manually creates an immutable version snapshot.
        """
        quiz = self.get_object()
        self.check_object_permissions(request, quiz)
        change_log = request.data.get("change_log")
        version_obj = VersionManager.create_snapshot(quiz, change_log=change_log, user=request.user)
        return Response(QuizVersionSerializer(version_obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        """
        Reorders questions in the quiz.
        Payload: {"ordered_ids": ["uuid_1", "uuid_2", ...]}
        """
        quiz = self.get_object()
        self.check_object_permissions(request, quiz)
        ordered_ids = request.data.get("ordered_ids", [])
        if not isinstance(ordered_ids, list):
            raise ValidationError({"ordered_ids": "Must be a list of question UUIDs."})
        updated_questions = QuizCRUD.reorder_questions(quiz, ordered_ids)
        return Response(QuestionSerializer(updated_questions, many=True).data)


class QuestionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing individual Questions.
    Enforces QuestionTypeRegistry validation and safety locks (is_locked).
    """

    queryset = Question.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return QuestionCreateUpdateSerializer
        return QuestionSerializer

    def perform_create(self, serializer):
        quiz = serializer.validated_data.get("quiz")
        if quiz.owner != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("You do not own this quiz.")
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        override_locked = self.request.data.get("override_locked", False)
        if instance.is_locked and not override_locked:
            raise ValidationError(
                {"is_locked": "Bu savol qulflangan (is_locked=True). Tahrirlash taqiqlanadi."}
            )
        serializer.save()

    def perform_destroy(self, instance):
        override_locked = self.request.data.get("override_locked", False)
        if instance.is_locked and not override_locked:
            raise ValidationError(
                {"is_locked": "Bu savol qulflangan (is_locked=True). O'chirish taqiqlanadi."}
            )
        instance.delete()
