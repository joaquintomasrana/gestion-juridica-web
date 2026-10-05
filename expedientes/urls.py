from django.urls import path
from . import views

app_name = 'expedientes'

urlpatterns = [
    path('', views.ExpedienteListView.as_view(), name='lista'),
]
