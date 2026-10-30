from django import forms

from .models import Expediente


class ExpedienteForm(forms.ModelForm):
    class Meta:
        model = Expediente
        fields = ['numero', 'caratula', 'fuero_juzgado', 'fecha_inicio', 'tipo_proceso', 'estado', 'observaciones']
