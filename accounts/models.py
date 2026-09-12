from django.conf import settings
from django.db import models

from .fields import EncryptedCharField


class Profile(models.Model):
    """
    One-to-one extension of Django's User, carrying the role that decides
    what a person can see: a student only ever sees their own file, a
    reviewer sees everyone assigned to them, an admin sees everything.
    """

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        REVIEWER = 'reviewer', 'Reviewer'
        ADMIN = 'admin', 'Admin'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.get_username()} ({self.get_role_display()})'

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_reviewer(self):
        return self.role in (self.Role.REVIEWER, self.Role.ADMIN)


class StudentDetail(models.Model):
    """
    The identity and enrollment record behind the checklist. Split out
    from Profile because reviewers need to read this but never touch
    Django's own auth tables, and because it holds the fields that need
    encryption or careful access-logging.
    """

    class LevelOfStudy(models.TextChoices):
        UNDERGRADUATE = 'undergraduate', 'Undergraduate'
        POSTGRADUATE = 'postgraduate', 'Postgraduate (Masters)'
        DOCTORAL = 'doctoral', 'Doctoral'
        EXCHANGE = 'exchange', 'Exchange / non-degree'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_detail')

    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)

    passport_number = EncryptedCharField()
    passport_issuing_country = models.CharField(max_length=100)
    passport_expiry = models.DateField()

    student_id_number = models.CharField(max_length=50)
    student_registration_number = models.CharField(max_length=50, blank=True)
    institution_name = models.CharField(max_length=200)
    course = models.CharField(max_length=200)
    year_of_study = models.PositiveSmallIntegerField()
    level_of_study = models.CharField(max_length=20, choices=LevelOfStudy.choices)

    student_email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Student record'

    def __str__(self):
        return f'{self.full_name} — {self.institution_name}'