from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentType(models.Model):
    """
    One row per checklist item. Kept as data rather than a hardcoded
    enum so admissions staff can add or retire requirements without a
    code change — e.g. a new intake year needing an extra form.
    """

    name = models.CharField(max_length=150, unique=True)
    description = models.CharField(max_length=300, blank=True)
    is_required = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Document(models.Model):
    """
    A single uploaded file against one checklist item for one student.
    The file itself lives in Supabase Storage; this row only ever holds
    the storage path plus review metadata.
    """

    class Status(models.TextChoices):
        NOT_SUBMITTED = 'not_submitted', 'Not submitted'
        PENDING = 'pending_review', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='documents')
    document_type = models.ForeignKey(DocumentType, on_delete=models.PROTECT, related_name='submissions')

    storage_path = models.CharField(max_length=500, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_SUBMITTED)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_documents'
    )
    review_note = models.TextField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'document_type')
        ordering = ['document_type__order']

    def __str__(self):
        return f'{self.student} — {self.document_type} ({self.get_status_display()})'

    def mark_submitted(self, storage_path, original_filename, content_type, file_size):
        self.storage_path = storage_path
        self.original_filename = original_filename
        self.content_type = content_type
        self.file_size = file_size
        self.status = self.Status.PENDING
        self.submitted_at = timezone.now()
        self.reviewer = None
        self.review_note = ''
        self.reviewed_at = None
        self.save()

    def approve(self, reviewer, note=''):
        self.status = self.Status.APPROVED
        self.reviewer = reviewer
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer, note):
        self.status = self.Status.REJECTED
        self.reviewer = reviewer
        self.review_note = note
        self.reviewed_at = timezone.now()
        self.save()


class AccessLog(models.Model):
    """
    Every time a signed URL is issued for a document, we log who asked
    for it. Sensitive-document access should be traceable even when
    nothing was changed — this is what an auditor asks for first.
    """

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='access_logs')
    accessed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-accessed_at']