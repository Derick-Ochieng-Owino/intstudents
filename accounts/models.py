from django.conf import settings
from django.db import models
from django.utils import timezone

from .fields import EncryptedCharField


class Profile(models.Model):
    """
    Extra information about an authenticated user.

    Django's User model remains responsible for authentication.
    Profile controls the application's role and account state.
    """

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        REVIEWER = 'reviewer', 'Reviewer'
        ADMIN = 'admin', 'Administrator'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_suspended = models.BooleanField(default=False)

    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_username()} ({self.get_role_display()})'

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_reviewer(self):
        return self.role in (
            self.Role.REVIEWER,
            self.Role.ADMIN,
        )

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    def mark_email_verified(self):
        if not self.email_verified_at:
            self.email_verified_at = timezone.now()
            self.save(
                update_fields=[
                    'email_verified_at',
                    'updated_at',
                ]
            )


class StudentDetail(models.Model):
    """
    Applicant/student identity and academic information.

    Sensitive identifying information is encrypted where appropriate.
    """

    class LevelOfStudy(models.TextChoices):
        UNDERGRADUATE = 'undergraduate', 'Undergraduate'
        POSTGRADUATE = 'postgraduate', 'Postgraduate (Masters)'
        DOCTORAL = 'doctoral', 'Doctoral'
        EXCHANGE = 'exchange', 'Exchange / non-degree'

    class VerificationStatus(models.TextChoices):
        INCOMPLETE = 'incomplete', 'Incomplete'
        SUBMITTED = 'submitted', 'Submitted'
        UNDER_REVIEW = 'under_review', 'Under review'
        ACTION_REQUIRED = 'action_required', 'Action required'
        PARTIALLY_VERIFIED = 'partially_verified', 'Partially verified'
        VERIFIED = 'verified', 'Verified'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_detail',
    )

    # ------------------------------------------------------------------
    # Personal information
    # ------------------------------------------------------------------

    full_name = models.CharField(max_length=200)

    date_of_birth = models.DateField()

    nationality = models.CharField(max_length=100)

    # ------------------------------------------------------------------
    # Passport information
    # ------------------------------------------------------------------

    passport_number = EncryptedCharField()

    passport_issuing_country = models.CharField(max_length=100)

    passport_expiry = models.DateField()

    # ------------------------------------------------------------------
    # Academic information
    # ------------------------------------------------------------------

    student_id_number = models.CharField(max_length=50)

    student_registration_number = models.CharField(
        max_length=50,
        blank=True,
    )

    institution_name = models.CharField(max_length=200)

    course = models.CharField(max_length=200)

    year_of_study = models.PositiveSmallIntegerField()

    level_of_study = models.CharField(
        max_length=20,
        choices=LevelOfStudy.choices,
    )

    student_email = models.EmailField()

    # ------------------------------------------------------------------
    # Immigration / residence information
    # ------------------------------------------------------------------

    visa_or_residence_type = models.CharField(
        max_length=150,
        blank=True,
    )

    visa_or_residence_expiry = models.DateField(
        null=True,
        blank=True,
    )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.INCOMPLETE,
    )

    verification_note = models.TextField(
        blank=True,
    )

    verification_updated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student record'
        verbose_name_plural = 'Student records'

    def __str__(self):
        return f'{self.full_name} — {self.institution_name}'

    def set_verification_status(self, status, note=''):
        self.verification_status = status
        self.verification_note = note
        self.verification_updated_at = timezone.now()

        self.save(
            update_fields=[
                'verification_status',
                'verification_note',
                'verification_updated_at',
                'updated_at',
            ]
        )


class EmailVerification(models.Model):
    """
    One-time email verification record.

    The raw token is never stored in the database.
    Only its hash is stored.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_verifications',
    )

    token_hash = models.CharField(
        max_length=64,
        unique=True,
    )

    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ['-created_at']

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.verified_at is not None

    def __str__(self):
        return f'Email verification for {self.user.get_username()}'