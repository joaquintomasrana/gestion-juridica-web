from django import forms

from .models import Expediente, Gasto, Honorario, Parte, PasoProcesal, Vencimiento


class FechaInput(forms.DateInput):
    """Selector de fecha del navegador (<input type="date">)."""
    input_type = "date"

    def __init__(self, **kwargs):
        # El navegador solo entiende AAAA-MM-DD; sin esto, al editar aparece vacío.
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class ExpedienteForm(forms.ModelForm):
    class Meta:
        model = Expediente
        fields = ['numero', 'caratula', 'fuero_juzgado', 'fecha_inicio', 'tipo_proceso', 'estado', 'observaciones']
        widgets = {
            "fecha_inicio": FechaInput(),
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


# Ninguno incluye el campo "expediente": se asigna en la vista, nunca desde el formulario.

class ParteForm(forms.ModelForm):
    class Meta:
        model = Parte
        fields = ["nombre", "tipo", "dni_cuit", "domicilio", "telefono", "email"]


class PasoProcesalForm(forms.ModelForm):
    class Meta:
        model = PasoProcesal
        fields = ["fecha", "descripcion", "observaciones"]
        widgets = {
            "fecha": FechaInput(),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }


class VencimientoForm(forms.ModelForm):
    class Meta:
        model = Vencimiento
        fields = ["fecha", "descripcion", "estado"]
        widgets = {"fecha": FechaInput()}


class HonorarioForm(forms.ModelForm):
    class Meta:
        model = Honorario
        fields = ["fecha", "monto", "moneda", "concepto", "forma_pago"]
        widgets = {"fecha": FechaInput()}


class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ["fecha", "monto", "moneda", "descripcion"]
        widgets = {"fecha": FechaInput()}
