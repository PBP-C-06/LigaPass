from django.contrib.auth.forms import UserCreationForm
from .models import User
from phonenumber_field.formfields import SplitPhoneNumberField

class RegisterForm(UserCreationForm):
    phone = SplitPhoneNumberField(region="ID")

    class Meta:
        model = User
        fields = ["username", "email", "phone", "password1", "password2"]
        labels = {
            "email": "Email address",
            "phone": "Phone Number",
        }
