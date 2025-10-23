from django import forms
from .models import News
from django.forms.widgets import ClearableFileInput

class PlainFileInput(ClearableFileInput):
    template_name = 'widgets/plain_file_input.html'

class NewsForm(forms.ModelForm):
    class Meta:
        model = News
        fields = ['title', 'content', 'category', 'thumbnail', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition',
                'placeholder': 'Masukkan judul berita...'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition',
                'rows': 6,
                'placeholder': 'Tulis isi berita...'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition'
            }),
            'thumbnail': PlainFileInput(),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
        }