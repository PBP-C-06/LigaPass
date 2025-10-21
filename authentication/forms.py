from django.contrib.auth.forms import UserCreationForm
from .models import User
from django import forms

class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ["username","first_name","last_name", "email", "password1", "password2"]
        labels = {
            "email": "Email address",
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email:
            if User.objects.filter(email=email).exists():
                existing_user = User.objects.get(email=email)
                if existing_user.is_google_account:
                    raise forms.ValidationError(
                        "This email is registered with Google. Please use Google Sign In."
                    )
                raise forms.ValidationError("User with this email already exists.")
        return email