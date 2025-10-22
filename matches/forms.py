from django import forms
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import Team, Match, TicketPrice, Venue

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'logo_url'] 
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input-class'}),
            'logo_url': forms.URLInput(attrs={'class': 'form-input-class'}),
        }

class TicketPriceBaseForm(forms.ModelForm):
    class Meta:
        model = TicketPrice
        fields = ['seat_category', 'price', 'quantity_available']
        
        error_messages = {
            'unique_together': {
                ('match', 'seat_category'): "Kategori tiket harus unik untuk setiap pertandingan (duplikasi terdeteksi)."
            }
        }

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['home_team', 'away_team', 'venue', 'date']
        widgets = {
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input-class'}),
            'home_team': forms.Select(attrs={'class': 'form-input-class'}),
            'away_team': forms.Select(attrs={'class': 'form-input-class'}),
            'venue': forms.Select(attrs={'class': 'form-input-class'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        home_team = cleaned_data.get("home_team")
        away_team = cleaned_data.get("away_team")

        if home_team and away_team and home_team == away_team:
            raise forms.ValidationError(
                "Tim Tuan Rumah (Home Team) tidak boleh sama dengan Tim Tamu (Away Team)."
            )
        return cleaned_data

class BaseTicketPriceFormSet(BaseInlineFormSet):
    default_error_messages = {
        'unique_together': "Duplikasi Kategori Tiket Ditemukan. Mohon periksa kembali kategori tiket yang Anda masukkan."
    } 

TicketPriceFormSet = inlineformset_factory(
    Match, 
    TicketPrice, 
    form=TicketPriceBaseForm, 
    fields=['seat_category', 'price', 'quantity_available'], 
    extra=3,
    can_delete=True,
    formset=BaseTicketPriceFormSet
)