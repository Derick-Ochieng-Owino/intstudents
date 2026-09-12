from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import SignUpForm, StudentDetailForm
from .models import Profile, StudentDetail


def signup(request):
    if request.user.is_authenticated:
        return redirect('documents:dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role=Profile.Role.STUDENT)
            login(request, user)
            messages.success(request, 'Welcome — let\'s get your details on file before you upload anything.')
            return redirect('accounts:complete_profile')
    else:
        form = SignUpForm()

    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def complete_profile(request):
    detail = StudentDetail.objects.filter(user=request.user).first()

    if request.method == 'POST':
        form = StudentDetailForm(request.POST, instance=detail)
        if form.is_valid():
            record = form.save(commit=False)
            record.user = request.user
            record.save()
            messages.success(request, 'Your details are saved. Now upload the documents on your checklist.')
            return redirect('documents:dashboard')
    else:
        form = StudentDetailForm(instance=detail)

    return render(request, 'accounts/complete_profile.html', {'form': form, 'detail': detail})