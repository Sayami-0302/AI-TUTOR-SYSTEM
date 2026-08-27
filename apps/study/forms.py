from django import forms
from .models import Subject, StudyTopic, StudyNote


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'semester', 'color', 'description', 'exam_date']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Operating Systems',
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500'
            }),
            'code': forms.TextInput(attrs={
                'placeholder': 'e.g. CS401',
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500'
            }),
            'semester': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'color': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Brief description of the subject...',
                'rows': 2,
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'exam_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
        }


class StudyTopicForm(forms.ModelForm):
    class Meta:
        model = StudyTopic
        fields = ['title', 'chapter_number', 'difficulty', 'status', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'e.g. CPU Scheduling Algorithms',
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'chapter_number': forms.NumberInput(attrs={
                'min': 1,
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'difficulty': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
            'description': forms.Textarea(attrs={
                'placeholder': 'Key points about this topic...',
                'rows': 2,
                'class': 'w-full px-4 py-2.5 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50'
            }),
        }