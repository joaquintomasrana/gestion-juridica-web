from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Expediente

User = get_user_model()


class AislamientoExpedientesTests(TestCase):
    def test_expediente_ajeno_responde_404(self):
        ana = User.objects.create_user("ana", password="x")
        beto = User.objects.create_user("beto", password="x")
        exp_beto = Expediente.objects.create(owner=beto, caratula="Ajeno")

        self.client.force_login(ana)
        url = reverse("expedientes:detalle", args=[exp_beto.pk])
        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 404)
