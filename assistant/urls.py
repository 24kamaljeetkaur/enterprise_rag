
from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("upload/", views.upload_pdf, name="upload_pdf"),
    path("documents/", views.document_list, name="document_list"),
    path(
        "documents/<int:pk>/delete/",
        views.delete_pdf,
        name="delete_pdf",
    ),
    path(
        "documents/<int:pk>/reindex/",
        views.reindex_pdf,
        name="reindex_pdf",
    ),
    path("chat/", views.chat, name="chat"),
]
