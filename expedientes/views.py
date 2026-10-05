from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Expediente

# Create your views here.

class ExpedienteListView(LoginRequiredMixin, ListView):
    model = Expediente
    template_name = "expedientes/expediente_list.html"
    context_object_name = "expedientes"
    
    def get_queryset(self):
        return Expediente.objects.filter(owner=self.request.user)
