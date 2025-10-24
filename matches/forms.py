from django import forms
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from .models import Team, Match, TicketPrice, Venue

class BaseTicketPriceFormSet(BaseInlineFormSet):
    
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seat_categories = []
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                seat_category = form.cleaned_data.get('seat_category')
                
                if seat_category in seat_categories:
                    raise ValidationError("Duplikasi Kategori Tiket Ditemukan. Setiap pertandingan hanya boleh memiliki satu kategori VVIP, VIP, dan Regular.")
                
                seat_categories.append(seat_category)
                
class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'logo_url', 'league']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input-class'}),
            'logo_url': forms.URLInput(attrs={
                'class': 'form-input-class',
                'placeholder': 'Kosongkan URL untuk mengambil logo dari folder static'
            }),
            'league': forms.Select(attrs={'class': 'form-input-class'}),
        }

class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['home_team', 'away_team', 'venue', 'date', 'home_goals', 'away_goals']
        widgets = {
            'date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-input-class'},
                format="%Y-%m-%dT%H:%M",
                ),
            'home_team': forms.Select(attrs={'class': 'form-input-class'}),
            'away_team': forms.Select(attrs={'class': 'form-input-class'}),
            'venue': forms.Select(attrs={'class': 'form-input-class'}),
            'home_goals': forms.NumberInput(attrs={'class': 'form-input-class', 'min': 0}),
            'away_goals': forms.NumberInput(attrs={'class': 'form-input-class', 'min': 0}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        home_team = cleaned_data.get("home_team")
        away_team = cleaned_data.get("away_team")

        if home_team and away_team and home_team == away_team:
            raise ValidationError(
                "Tim Tuan Rumah (Home Team) tidak boleh sama dengan Tim Tamu (Away Team)."
            )

        return cleaned_data
    
TicketPriceFormSet = inlineformset_factory(
    Match, 
    TicketPrice, 
    formset=BaseTicketPriceFormSet,
    fields=['seat_category', 'price', 'quantity_available'], 
    extra=0,
    can_delete=True
)