from django.urls import path
from .views import (
    quiz_list_create_view,
    quiz_detail_view,
    quiz_add_question_view,
    question_detail_view,
    quiz_snapshot_view,
    quiz_version_list_view,
    quiz_student_preview_view,
    upload_question_image_view,
)

app_name = "quizzes"

urlpatterns = [
    path("", quiz_list_create_view, name="quiz_list_create"),
    path("upload-image/", upload_question_image_view, name="quiz_upload_image"),
    path("<uuid:pk>/", quiz_detail_view, name="quiz_detail"),
    path("<uuid:pk>/questions/", quiz_add_question_view, name="quiz_add_question"),
    path("<uuid:quiz_pk>/questions/<uuid:question_pk>/", question_detail_view, name="question_detail"),
    path("<uuid:pk>/snapshot/", quiz_snapshot_view, name="quiz_snapshot"),
    path("<uuid:pk>/versions/", quiz_version_list_view, name="quiz_versions"),
    path("<uuid:pk>/preview/", quiz_student_preview_view, name="quiz_student_preview"),
]
