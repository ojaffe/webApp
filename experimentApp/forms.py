from django import forms

from .models import Experiment, EmailModel


# Form to validate experiment fields
class ExperimentForm(forms.ModelForm):

    class Meta:
        model = Experiment
        fields = ['experiment_title', 'experiment_description']


# Form to collect ordering of ranking questions
class OrderingForm(forms.Form):
    ordering = forms.CharField()


# Used to get validation errors
class EmailForm(forms.ModelForm):

    class Meta:
        model = EmailModel
        fields = ['subject', 'message']
