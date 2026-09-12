from django import forms
from django.conf import settings

ALLOWED_CONTENT_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
}
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}


class DocumentUploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        f = self.cleaned_data['file']

        ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('Only PDF, JPG, or PNG files are accepted.')

        if f.content_type not in ALLOWED_CONTENT_TYPES:
            raise forms.ValidationError('That file type is not allowed. Please upload a PDF, JPG, or PNG.')

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if f.size > max_bytes:
            raise forms.ValidationError(f'File is too large. Maximum size is {settings.MAX_UPLOAD_MB} MB.')

        return f


class ReviewForm(forms.Form):
    DECISION_CHOICES = (('approve', 'Approve'), ('reject', 'Reject'))

    decision = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    note = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'reject' and not cleaned.get('note'):
            raise forms.ValidationError('Please explain why the document is being rejected — the student needs to know what to fix.')
        return cleaned