from django.contrib.auth.forms import UserCreationForm
from .models import User
from django import forms

class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        ]
        labels = {
            "email": "Email address",
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_messages['password_mismatch'] = 'Password tidak sama.'

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            existing_user = User.objects.get(email=email)
            if existing_user.is_google_account:
                raise forms.ValidationError(
                    "Email ini terdaftar melalui Google. Silakan login dengan Google."
                )
            raise forms.ValidationError("Email sudah digunakan.")
        return email

    def clean(self):
        cleaned_data = super().clean()

        if "password2" in self.errors:
            password_errors = self.errors.get("password2")
            for err in password_errors:
                self.add_error("password1", err)

            del self.errors["password2"]

        return cleaned_data
