from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import StudentDetail


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='Use the email address you check regularly — we send status updates here.')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class StudentDetailForm(forms.ModelForm):
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    passport_expiry = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = StudentDetail
        exclude = ('user', 'created_at', 'updated_at')
        widgets = {
            'nationality': forms.TextInput(attrs={'placeholder': 'e.g. Kenyan'}),
            'passport_number': forms.TextInput(attrs={'autocomplete': 'off'}),
        }