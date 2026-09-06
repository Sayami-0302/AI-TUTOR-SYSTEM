from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, get_user_model, update_session_auth_hash
from django.contrib import messages
from django.views import View
from .forms import RegistrationForm, LoginForm, CustomPasswordChangeForm

User = get_user_model()


class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = RegistrationForm()
        return render(request, 'accounts/register.html', {'form': form})

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            username = form.cleaned_data['username']
            full_name = form.cleaned_data['full_name']
            password = form.cleaned_data['password']

            if User.objects.filter(email=email).exists():
                messages.error(request, "Email already exists.")
                return render(request, 'accounts/register.html', {'form': form})

            if User.objects.filter(username=username).exists():
                messages.error(request, "Username already exists.")
                return render(request, 'accounts/register.html', {'form': form})

            User.objects.create_user(
                email=email,
                username=username,
                full_name=full_name,
                password=password,
            )
            messages.success(request, "Registration successful! Please sign in.")
            return redirect('login')
        return render(request, 'accounts/register.html', {'form': form})


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = LoginForm()
        return render(request, 'accounts/login.html', {'form': form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, email=email, password=password)
            if user:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid email or password.")
        return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Cleanly terminates the user session and redirects to login"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('login')


class ProfileView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        active_tab = request.GET.get('tab', 'details')
        password_form = CustomPasswordChangeForm(user=request.user)
        return render(request, 'accounts/profile.html', {
            'user': request.user,
            'password_form': password_form,
            'active_tab': active_tab,
        })

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        password_form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed successfully!")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors in the password change form.")
            return render(request, 'accounts/profile.html', {
                'user': request.user,
                'password_form': password_form,
                'active_tab': 'password',
            })