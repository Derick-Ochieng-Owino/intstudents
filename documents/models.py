from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentType(models.Model):
    """
    Defines a document requirement.

    Examples:
    - Passport bio page
    - Proof of enrollment
    - Visa or residence permit
    - Official university nationality document
    """

    name = models.CharField(
        max_length=150,
        unique=True,
    )

    description = models.CharField(
        max_length=300,
        blank=True,
    )

    is_required = models.BooleanField(
        default=True,
    )

    order = models.PositiveSmallIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Document(models.Model):
    """
    Current state of a student's document requirement.

    This remains one row per student + document requirement.

    Actual uploaded versions are stored in DocumentSubmission.
    """

    class Status(models.TextChoices):
        NOT_SUBMITTED = 'not_submitted', 'Not submitted'
        PENDING = 'pending_review', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents',
    )

    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='documents',
    )

    # Current/latest file
    storage_path = models.CharField(
        max_length=500,
        blank=True,
    )

    original_filename = models.CharField(
        max_length=255,
        blank=True,
    )

    content_type = models.CharField(
        max_length=100,
        blank=True,
    )

    file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_SUBMITTED,
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_documents',
    )

    review_note = models.TextField(
        blank=True,
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'document_type'],
                name='unique_student_document_type',
            ),
        ]

        ordering = [
            'document_type__order',
        ]

    def __str__(self):
        return (
            f'{self.student} — '
            f'{self.document_type} '
            f'({self.get_status_display()})'
        )

    @property
    def is_submitted(self):
        return bool(self.storage_path)

    def mark_submitted(
        self,
        storage_path,
        original_filename,
        content_type,
        file_size,
    ):
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


class DocumentSubmission(models.Model):
    """
    Historical record of every uploaded version of a document.

    A rejected document is never silently destroyed when the student
    uploads a replacement.
    """

    document = models.ForeignKey(Document,on_delete=models.CASCADE,related_name='submissions',)
    version = models.PositiveIntegerField(default=1,)
    storage_path = models.CharField(max_length=500,)
    original_filename = models.CharField(max_length=255,)
    content_type = models.CharField(max_length=100,)
    file_size = models.PositiveIntegerField()

    class Status(models.TextChoices):
        PENDING = 'pending_review', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_submissions',
    )

    review_note = models.TextField(
        blank=True,
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True,
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-version']

        constraints = [
            models.UniqueConstraint(
                fields=['document', 'version'],
                name='unique_document_version',
            ),
        ]

    def __str__(self):
        return (
            f'{self.document} — '
            f'v{self.version} '
            f'({self.get_status_display()})'
        )


class AccessLog(models.Model):
    # Records access to sensitive uploaded documents.

    document = models.ForeignKey(Document,on_delete=models.CASCADE,related_name='access_logs',)
    accessed_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,)
    accessed_at = models.DateTimeField(auto_now_add=True,)

    class Meta:
        ordering = ['-accessed_at']

    def __str__(self):
        return (
            f'{self.accessed_by} accessed '
            f'{self.document}'
        )