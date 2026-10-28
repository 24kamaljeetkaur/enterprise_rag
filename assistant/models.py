
from django.db import models


class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    file_hash = models.CharField(
        max_length=64,
        unique=True,
    )
    chunk_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        default="pending",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class ChatMessage(models.Model):
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat {self.pk} - {self.created_at}"
