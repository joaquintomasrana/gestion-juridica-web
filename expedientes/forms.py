from django import forms

from .models import Expediente


class ExpedienteForm(forms.ModelForm):
    class Meta:
        model = Expediente
        fields = ['numero', 'caratula', 'fuero_juzgado', 'fecha_inicio', 'tipo_proceso', 'estado', 'observaciones']
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
