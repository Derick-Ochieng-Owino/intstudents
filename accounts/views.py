import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import (
    EmailOrUsernameLoginForm,
    SignUpForm,
    StudentDetailForm,
)
from .models import EmailVerification, Profile, StudentDetail


VERIFICATION_TOKEN_HOURS = 24


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def can_access_dashboard(user):
    if not user.is_authenticated:
        return False
    
    # Allow superusers, staff, or specific roles defined on your Profile model
    if user.is_superuser or user.is_staff:
        return True
    
    # Check if the user has an allowed role on their Profile
    profile = getattr(user, 'profile', None)
    if profile and profile.role in ['admin', 'reviewer', 'staff']:  # adjust to your choices
        return True
        
    return False

def _create_verification(user):
    """
    Create a new email verification token.

    Only the hash is stored in the database.
    The original token is sent to the user's email.
    """

    # Invalidate previous unused tokens.
    EmailVerification.objects.filter(
        user=user,
        verified_at__isnull=True,
    ).update(
        expires_at=timezone.now()
    )

    raw_token = secrets.token_urlsafe(48)

    verification = EmailVerification.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),
        expires_at=timezone.now()
        + timedelta(hours=VERIFICATION_TOKEN_HOURS),
    )

    return verification, raw_token


def _send_verification_email(request, user, raw_token):
    verification_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={
                "token": raw_token,
            },
        )
    )

    subject = "Verify your IntStudents account"

    message = f"""
Hello {user.username},

Welcome to IntStudents.

Please verify your email address by opening the link below:

{verification_url}

This link expires in {VERIFICATION_TOKEN_HOURS} hours.

If you did not create this account, you can safely ignore this email.

Regards,
IntStudents
""".strip()

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )

def login_view(request):
    if request.user.is_authenticated:
        return redirect("documents:dashboard")

    if request.method == "POST":
        form = EmailOrUsernameLoginForm(
            request=request,
            data=request.POST,
        )

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            return redirect("documents:dashboard")

    else:
        form = EmailOrUsernameLoginForm(request=request)

    return render(
        request,
        "accounts/login.html",
        {"form": form},
    )

def signup(request):
    if request.user.is_authenticated:
        return redirect("documents:dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()

            profile = Profile.objects.create(
                user=user,
                role=Profile.Role.STUDENT,
            )

            verification, raw_token = _create_verification(user)

            try:
                _send_verification_email(
                    request,
                    user,
                    raw_token,
                )
            except Exception:
                # Remove the account if email delivery fails during
                # development/registration. This prevents an account
                # from being created that cannot be verified.
                verification.delete()
                profile.delete()
                user.delete()

                messages.error(
                    request,
                    "We could not send the verification email. "
                    "Please check the email configuration and try again.",
                )

                return render(
                    request,
                    "accounts/signup.html",
                    {"form": form},
                )

            messages.success(
                request,
                "Account created. Check your email for the verification link.",
            )

            return redirect("accounts:verification_sent")

    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form},
    )


def verification_sent(request):
    return render(
        request,
        "accounts/verification_sent.html",
    )


def verify_email(request, token):
    token_hash = _hash_token(token)

    verification = (
        EmailVerification.objects
        .select_related("user", "user__profile")
        .filter(
            token_hash=token_hash,
            verified_at__isnull=True,
        )
        .first()
    )

    if verification is None:
        return render(
            request,
            "accounts/email_verification_invalid.html",
            {
                "reason": "invalid",
            },
        )

    if verification.is_expired:
        return render(
            request,
            "accounts/email_verification_invalid.html",
            {
                "reason": "expired",
            },
        )

    user = verification.user
    profile = user.profile

    # Never reactivate an account that an administrator has suspended.
    if profile.is_suspended:
        return render(
            request,
            "accounts/email_verification_invalid.html",
            {
                "reason": "suspended",
            },
        )

    verification.verified_at = timezone.now()
    verification.save(update_fields=["verified_at"])

    profile.mark_email_verified()

    user.is_active = True
    user.save(update_fields=["is_active"])

    messages.success(
        request,
        "Your email has been verified. You can now sign in.",
    )

    return redirect("accounts:login")


@login_required
def complete_profile(request):
    # Fetch existing profile details if present; do not insert an empty row
    detail = StudentDetail.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = StudentDetailForm(
            request.POST,
            request.FILES,
            instance=detail,
        )

        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.save()

            messages.success(
                request,
                "Your details are saved. "
                "Now upload the documents on your checklist.",
            )

            return redirect("documents:dashboard")

    else:
        form = StudentDetailForm(instance=detail)

    return render(
        request,
        "accounts/complete_profile.html",
        {
            "form": form,
            "detail": detail,
        },
    )