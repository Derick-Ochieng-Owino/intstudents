from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


app_name = "accounts"


urlpatterns = [
    path(
        "signup/",
        views.signup,
        name="signup",
    ),

    path(
        "verification-sent/",
        views.verification_sent,
        name="verification_sent",
    ),

    path(
        "verify-email/<str:token>/",
        views.verify_email,
        name="verify_email",
    ),

    path("login/", views.login_view, name="login"),
    
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    path(
        "profile/",
        views.complete_profile,
        name="complete_profile",
    ),
]