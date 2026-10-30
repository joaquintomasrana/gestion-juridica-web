from django import forms

from .models import Expediente


class ExpedienteForm(forms.ModelForm):
    class Meta:
        model = Expediente
        fields = ['numero', 'caratula', 'fuero_juzgado', 'fecha_inicio', 'tipo_proceso', 'estado', 'observaciones']
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        
    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_numero(self):
        numero = self.cleaned_data.get("numero")
        if not numero:
            return None
        repetidos = Expediente.objects.filter(owner=self.owner, numero=numero)
        if self.instance.pk:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise forms.ValidationError("Ya tenés un expediente con ese número.")
        return numero