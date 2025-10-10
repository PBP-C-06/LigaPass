from django import forms
from django.contrib.auth import get_user_model
from django.utils.html import strip_tags

User = get_user_model()

class UserEditForm(forms.ModelForm):
    profile_picture = forms.ImageField(required=False)
    phone_number = forms.CharField(required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

    # Menggunakan strip_tags dengan prevensi untuk data yang kosong 
    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '')
        return strip_tags(first_name)

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '')
        return strip_tags(last_name)

    def clean_username(self):
        username = self.cleaned_data.get('username', '')
        return strip_tags(username)

    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        return strip_tags(email)
