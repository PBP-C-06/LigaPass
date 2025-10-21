from django import forms
from .models import Team

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['api_id', 'name', 'logo_url']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input-class'}),
            'api_id': forms.NumberInput(attrs={'class': 'form-input-class'}),
            'logo_url': forms.URLInput(attrs={'class': 'form-input-class'}),
        }