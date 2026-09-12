from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import DocumentUploadForm, ReviewForm
from .models import AccessLog, Document, DocumentType
from .storage import StorageError, build_path, signed_url, upload as storage_upload


def reviewer_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if not profile or not profile.is_reviewer:
            return HttpResponseForbidden('Reviewer access only.')
        return view_func(request, *args, **kwargs)
    return login_required(wrapped)


def _checklist_for(user):
    existing = {d.document_type_id: d for d in Document.objects.filter(student=user)}
    rows = []
    for dtype in DocumentType.objects.filter(is_required=True):
        rows.append(existing.get(dtype.id) or Document(student=user, document_type=dtype))
    return rows


@login_required
def dashboard(request):
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_reviewer:
        return redirect('documents:reviewer_queue')

    if not hasattr(request.user, 'student_detail'):
        messages.info(request, 'Please complete your details first.')
        return redirect('accounts:complete_profile')

    checklist = _checklist_for(request.user)
    approved = sum(1 for d in checklist if d.status == Document.Status.APPROVED)

    return render(request, 'documents/dashboard.html', {
        'checklist': checklist,
        'total': len(checklist),
        'approved': approved,
    })


@login_required
def upload_document(request, type_id):
    dtype = get_object_or_404(DocumentType, pk=type_id)
    document, _ = Document.objects.get_or_create(student=request.user, document_type=dtype)

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data['file']
            path = build_path(request.user.id, dtype.id, f.name)
            try:
                content_type, size = storage_upload(f, path)
            except StorageError as exc:
                messages.error(request, str(exc))
                return redirect('documents:dashboard')

            document.mark_submitted(path, f.name, content_type, size)
            messages.success(request, f'"{dtype.name}" uploaded and is now pending review.')
            return redirect('documents:dashboard')
    else:
        form = DocumentUploadForm()

    return render(request, 'documents/upload.html', {'form': form, 'document_type': dtype, 'document': document})


@login_required
def view_document(request, pk):
    document = get_object_or_404(Document, pk=pk)

    profile = getattr(request.user, 'profile', None)
    is_owner = document.student_id == request.user.id
    is_reviewer = profile and profile.is_reviewer
    if not (is_owner or is_reviewer):
        return HttpResponseForbidden()

    if not document.storage_path:
        messages.error(request, 'Nothing has been uploaded for this item yet.')
        return redirect('documents:dashboard')

    try:
        url = signed_url(document.storage_path)
    except StorageError as exc:
        messages.error(request, str(exc))
        return redirect('documents:dashboard')

    AccessLog.objects.create(document=document, accessed_by=request.user)
    return HttpResponseRedirect(url)


@reviewer_required
def reviewer_queue(request):
    status_filter = request.GET.get('status', Document.Status.PENDING)
    documents = Document.objects.exclude(storage_path='').select_related('student', 'document_type')
    if status_filter != 'all':
        documents = documents.filter(status=status_filter)

    return render(request, 'documents/reviewer_queue.html', {
        'documents': documents,
        'status_filter': status_filter,
        'statuses': Document.Status.choices,
    })


@reviewer_required
def review_document(request, pk):
    document = get_object_or_404(Document, pk=pk)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            note = form.cleaned_data['note']
            if form.cleaned_data['decision'] == 'approve':
                document.approve(reviewer=request.user, note=note)
                verdict = 'approved'
            else:
                document.reject(reviewer=request.user, note=note)
                verdict = 'rejected'

            _notify_student(document, verdict)
            messages.success(request, f'Marked "{document.document_type.name}" as {verdict}.')
            return redirect('documents:reviewer_queue')
    else:
        form = ReviewForm()

    return render(request, 'documents/review_document.html', {'form': form, 'document': document})


def _notify_student(document, verdict):
    subject = f'Update on your "{document.document_type.name}" submission'
    if verdict == 'approved':
        body = f'Good news — your "{document.document_type.name}" has been approved.'
    else:
        body = (
            f'Your "{document.document_type.name}" was not approved.\n\n'
            f'Reviewer note: {document.review_note}\n\n'
            'Please log in and re-upload a corrected version.'
        )
    send_mail(
        subject,
        body,
        None,
        [document.student.email],
        fail_silently=True,
    )