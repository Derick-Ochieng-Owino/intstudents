from functools import wraps
from django.http import FileResponse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

import os
from django.core.files.storage import default_storage

from accounts.models import StudentDetail, Profile
from .models import (
    AccessLog,
    Document,
    DocumentSubmission,
    DocumentType,
)

from .forms import DocumentUploadForm, ReviewForm
from .models import AccessLog, Document, DocumentSubmission, DocumentType
from .storage import delete, signed_url, upload


def reviewer_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)

        if not profile or not profile.is_reviewer:
            messages.error(
                request,
                "You do not have permission to access the reviewer area.",
            )
            return redirect("documents:dashboard")

        if profile.is_suspended:
            messages.error(
                request,
                "Your account has been suspended.",
            )
            return redirect("accounts:login")

        return view_func(request, *args, **kwargs)

    return wrapper


def _checklist_for(user):
    document_types = DocumentType.objects.filter(
        is_active=True,
        is_required=True,
    )

    checklist = []

    for document_type in document_types:
        document, _ = Document.objects.get_or_create(
            student=user,
            document_type=document_type,
        )

        checklist.append(document)

    return checklist


@login_required
def dashboard(request):
    """
    Main student dashboard.

    Flow:
    - Reviewers/admins go to reviewer queue.
    - Students without a profile are sent to complete their profile.
    - Students with a profile see their document checklist.
    """

    profile = getattr(request.user, "profile", None)

    if profile and profile.is_suspended:
        messages.error(
            request,
            "Your account has been suspended. Please contact an administrator.",
        )
        return redirect("accounts:login")

    if profile and profile.is_reviewer:
        return redirect("documents:reviewer_queue")

    detail = StudentDetail.objects.filter(
        user=request.user
    ).first()

    if not detail:
        messages.info(
            request,
            "Please complete your student profile before uploading documents.",
        )
        return redirect("accounts:complete_profile")

    checklist = _checklist_for(request.user)

    submitted_count = sum(
        1 for document in checklist if document.is_submitted
    )

    approved_count = sum(
        1
        for document in checklist
        if document.status == Document.Status.APPROVED
    )

    rejected_count = sum(
        1
        for document in checklist
        if document.status == Document.Status.REJECTED
    )

    context = {
        "detail": detail,
        "checklist": checklist,
        "submitted_count": submitted_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "total_documents": len(checklist),
    }

    return render(
        request,
        "documents/dashboard.html",
        context,
    )

@login_required
def upload_document(request, type_id):
    if not hasattr(request.user, "student_detail"):
        return redirect("accounts:complete_profile")

    student = request.user

    document_type = get_object_or_404(
        DocumentType,
        id=type_id,
        is_active=True,
    )

    document, created = Document.objects.get_or_create(
        student=student,
        document_type=document_type,
        defaults={
            "status": Document.Status.NOT_SUBMITTED,
        },
    )

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            messages.error(
                request,
                "Please select a document to upload.",
            )
            return redirect(
                "documents:upload",
                type_id=document_type.id,
            )

        # Allowed file types
        allowed_extensions = {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
        }

        filename = uploaded_file.name
        extension = os.path.splitext(filename)[1].lower()

        if extension not in allowed_extensions:
            messages.error(
                request,
                "Invalid file type. Please upload a PDF, JPG, JPEG or PNG file.",
            )
            return redirect(
                "documents:upload",
                type_id=document_type.id,
            )

        # Maximum file size: 10 MB
        max_size = 10 * 1024 * 1024

        if uploaded_file.size > max_size:
            messages.error(
                request,
                "The file is too large. The maximum allowed size is 10 MB.",
            )
            return redirect(
                "documents:upload",
                type_id=document_type.id,
            )

        # Determine next version
        last_submission = (
            document.submissions
            .order_by("-version")
            .first()
        )

        next_version = (
            last_submission.version + 1
            if last_submission
            else 1
        )

        # Storage path
        storage_path = (
            f"documents/"
            f"{student.id}/"
            f"{document_type.id}/"
            f"v{next_version}{extension}"
        )

        # Save file using the configured Django storage backend
        saved_path = default_storage.save(
            storage_path,
            uploaded_file,
        )

        now = timezone.now()

        # Update current document
        document.storage_path = saved_path
        document.original_filename = filename
        document.content_type = uploaded_file.content_type or ""
        document.file_size = uploaded_file.size
        document.status = Document.Status.PENDING
        document.reviewer = None
        document.review_note = ""
        document.submitted_at = now
        document.reviewed_at = None
        document.save()

        # Create version history
        DocumentSubmission.objects.create(
            document=document,
            version=next_version,
            storage_path=saved_path,
            original_filename=filename,
            content_type=uploaded_file.content_type or "",
            file_size=uploaded_file.size,
            status=DocumentSubmission.Status.PENDING,
            submitted_at=now,
        )

        _update_student_verification_status(student)

        messages.success(
            request,
            f"{document_type.name} uploaded successfully and submitted for review.",
        )

        return redirect("documents:dashboard")

    return render(
        request,
        "documents/upload.html",
        {
            "document": document,
            "document_type": document_type,
        },
    )

@login_required
def admin_dashboard(request):
    profile = getattr(request.user, "profile", None)

    if not profile or not (
        profile.is_admin or profile.is_reviewer
    ):
        messages.error(
            request,
            "You are not authorized to access the reviewer dashboard.",
        )
        return redirect("documents:dashboard")

    documents = (
        Document.objects
        .select_related(
            "student",
            "document_type",
            "reviewer",
        )
        .order_by("-submitted_at", "-updated_at")
    )

    pending_documents = documents.filter(
        status=Document.Status.PENDING
    )

    rejected_documents = documents.filter(
        status=Document.Status.REJECTED
    )

    approved_documents = documents.filter(
        status=Document.Status.APPROVED
    )

    students = (
        StudentDetail.objects
        .select_related("user")
        .order_by("-updated_at")
    )

    context = {
        "documents": documents,
        "pending_documents": pending_documents,
        "rejected_documents": rejected_documents,
        "approved_documents": approved_documents,
        "students": students,
        "total_students": students.count(),
        "total_documents": documents.count(),
        "pending_count": pending_documents.count(),
        "approved_count": approved_documents.count(),
        "rejected_count": rejected_documents.count(),
    }

    return render(
        request,
        "documents/admin_dashboard.html",
        context,
    )

@login_required
def view_document(request, pk):
    document = get_object_or_404(
        Document.objects.select_related(
            "student",
            "document_type",
        ),
        pk=pk,
    )

    profile = getattr(request.user, "profile", None)

    # Student access: only their own documents
    if document.student == request.user:
        allowed = True

    # Admin/reviewer access
    elif profile and (
        profile.is_admin or profile.is_reviewer
    ):
        allowed = True

    else:
        allowed = False

    if not allowed:
        messages.error(
            request,
            "You are not authorized to access this document.",
        )
        return redirect("documents:dashboard")

    if not document.storage_path:
        messages.error(
            request,
            "This document does not have an uploaded file.",
        )
        return redirect("documents:dashboard")

    try:
        file_object = default_storage.open(
            document.storage_path,
            "rb",
        )
    except Exception:
        messages.error(
            request,
            "The document could not be retrieved.",
        )
        return redirect("documents:dashboard")

    # Record access
    AccessLog.objects.create(
        document=document,
        accessed_by=request.user,
    )

    content_type = (
        document.content_type
        or "application/octet-stream"
    )

    response = FileResponse(
        file_object,
        content_type=content_type,
    )

    response["Content-Disposition"] = (
        f'inline; filename="{document.original_filename}"'
    )

    return response

@reviewer_required
def reviewer_queue(request):
    status = request.GET.get("status", "").strip()

    documents = (
        Document.objects
        .select_related(
            "student",
            "student__profile",
            "document_type",
            "reviewer",
        )
        .filter(storage_path__isnull=False)
        .exclude(storage_path="")
        .order_by("-submitted_at")
    )

    if status:
        valid_statuses = {
            choice[0]
            for choice in Document.Status.choices
        }

        if status in valid_statuses:
            documents = documents.filter(status=status)

    context = {
        "documents": documents,
        "current_status": status,
        "status_choices": Document.Status.choices,
    }

    return render(
        request,
        "documents/reviewer_queue.html",
        context,
    )


@reviewer_required
def review_document(request, document_id):
    document = get_object_or_404(
        Document.objects.select_related(
            "student",
            "document_type",
        ),
        id=document_id,
    )

    if not document.storage_path:
        messages.error(
            request,
            "This document has no uploaded file.",
        )
        return redirect("documents:reviewer_queue")

    if request.method == "POST":
        form = ReviewForm(request.POST)

        if form.is_valid():
            action = form.cleaned_data["action"]
            review_note = form.cleaned_data["review_note"]

            if action == "approve":
                document.approve(
                    reviewer=request.user,
                    note=review_note,
                )

                _sync_latest_submission(
                    document=document,
                    status=DocumentSubmission.Status.APPROVED,
                    reviewer=request.user,
                    note=review_note,
                )

                _notify_student(
                    document=document,
                    subject="Document approved",
                    message=(
                        f"Your document '{document.document_type.name}' "
                        "has been approved."
                    ),
                )

                messages.success(
                    request,
                    "Document approved successfully.",
                )

            else:
                document.reject(
                    reviewer=request.user,
                    note=review_note,
                )

                _sync_latest_submission(
                    document=document,
                    status=DocumentSubmission.Status.REJECTED,
                    reviewer=request.user,
                    note=review_note,
                )

                _notify_student(
                    document=document,
                    subject="Action required on your document",
                    message=(
                        f"Your document '{document.document_type.name}' "
                        "requires attention.\n\n"
                        f"Reviewer note:\n{review_note}"
                    ),
                )

                messages.warning(
                    request,
                    "Document rejected and the student has been notified.",
                )

            _update_student_verification_status(document.student)

            return redirect(
                "documents:review_document",
                document_id=document.id,
            )

    else:
        form = ReviewForm()

    context = {
        "document": document,
        "form": form,
    }

    return render(
        request,
        "documents/review_document.html",
        context,
    )


def _sync_latest_submission(
    document,
    status,
    reviewer,
    note,
):
    submission = (
        DocumentSubmission.objects
        .filter(document=document)
        .order_by("-version")
        .first()
    )

    if not submission:
        return

    submission.status = status
    submission.reviewer = reviewer
    submission.review_note = note
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=[
            "status",
            "reviewer",
            "review_note",
            "reviewed_at",
        ]
    )


def _update_student_verification_status(user):
    detail = StudentDetail.objects.filter(
        user=user
    ).first()

    if not detail:
        return

    documents = list(
        Document.objects.filter(
            student=user,
            document_type__is_active=True,
            document_type__is_required=True,
        )
    )

    if not documents:
        detail.set_verification_status(
            StudentDetail.VerificationStatus.INCOMPLETE
        )
        return

    submitted = [
        document
        for document in documents
        if document.is_submitted
    ]

    rejected = [
        document
        for document in documents
        if document.status == Document.Status.REJECTED
    ]

    approved = [
        document
        for document in documents
        if document.status == Document.Status.APPROVED
    ]

    if rejected:
        status = StudentDetail.VerificationStatus.ACTION_REQUIRED
    elif len(approved) == len(documents):
        status = StudentDetail.VerificationStatus.VERIFIED
    elif approved:
        status = StudentDetail.VerificationStatus.PARTIALLY_VERIFIED
    elif submitted:
        status = StudentDetail.VerificationStatus.UNDER_REVIEW
    else:
        status = StudentDetail.VerificationStatus.INCOMPLETE

    detail.set_verification_status(status)


def _notify_student(document, subject, message):
    student = document.student

    if not student.email:
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[student.email],
            fail_silently=True,
        )
    except Exception:
        pass