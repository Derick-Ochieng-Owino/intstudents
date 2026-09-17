from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import StudentDetail


class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text="Use an email address you can access. "
                  "We will send a verification link here."
    )

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists."
            )

        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "This username is already taken."
            )

        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False

        if commit:
            user.save()

        return user

class EmailOrUsernameLoginForm(AuthenticationForm):
    """
    Allows users to sign in using either their Django username
    or the email address attached to their account.
    """

    username = forms.CharField(
        label="Email or username",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter your email or username",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )

    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )

    def clean(self):
        username_or_email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username_or_email and password:

            identifier = username_or_email.strip()

            user = None

            # First try the identifier as a normal username.
            user = authenticate(
                self.request,
                username=identifier,
                password=password,
            )

            # If that fails, look for an account using the email.
            if user is None and "@" in identifier:

                matching_user = User.objects.filter(
                    email__iexact=identifier
                ).first()

                if matching_user:
                    user = authenticate(
                        self.request,
                        username=matching_user.get_username(),
                        password=password,
                    )

            if user is None:
                raise forms.ValidationError(
                    "Invalid email/username or password.",
                    code="invalid_login",
                )

            self.confirm_login_allowed(user)
            self.user_cache = user

        return self.cleaned_data

    def get_user(self):
        return self.user_cache

class StudentDetailForm(forms.ModelForm):
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"})
    )

    passport_expiry = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = StudentDetail
        exclude = ("user", "created_at", "updated_at")
        widgets = {
            "nationality": forms.TextInput(
                attrs={"placeholder": "e.g. Kenyan"}
            ),
            "passport_number": forms.TextInput(
                attrs={"autocomplete": "off"}
            ),
            "visa_or_residence_expiry": forms.DateInput(
                attrs={"type": "date"}
            ),
        }