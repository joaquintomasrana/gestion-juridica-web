from django.contrib.auth.forms import UserCreationForm
from django.views.generic import CreateView
from django.urls import reverse_lazy


class RegistroView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/registro.html"
    success_url = reverse_lazy("login")

