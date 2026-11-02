from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Expediente

User = get_user_model()


class DosUsuariosTestCase(TestCase):
    """Base: dos usuarios, cada uno con un expediente."""

    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user("ana", password="x")
        cls.beto = User.objects.create_user("beto", password="x")
        cls.exp_ana = Expediente.objects.create(
            owner=cls.ana, caratula="Gomez c/ Perez", numero="100/2026"
        )
        cls.exp_beto = Expediente.objects.create(
            owner=cls.beto, caratula="Lopez c/ Diaz", numero="200/2026"
        )


class AccesoSinSesionTests(DosUsuariosTestCase):
    def test_sin_sesion_redirige_al_login(self):
        urls = [
            reverse("expedientes:lista"),
            reverse("expedientes:nuevo"),
            reverse("expedientes:detalle", args=[self.exp_ana.pk]),
            reverse("expedientes:editar", args=[self.exp_ana.pk]),
            reverse("expedientes:eliminar", args=[self.exp_ana.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertRedirects(respuesta, f"{reverse('login')}?next={url}")


class AislamientoExpedientesTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_el_listado_solo_muestra_los_propios(self):
        respuesta = self.client.get(reverse("expedientes:lista"))
        self.assertContains(respuesta, "Gomez c/ Perez")
        self.assertNotContains(respuesta, "Lopez c/ Diaz")

    def test_la_busqueda_no_trae_expedientes_ajenos(self):
        respuesta = self.client.get(reverse("expedientes:lista"), {"q": "Lopez"})
        self.assertNotContains(respuesta, "Lopez c/ Diaz")

    def test_expediente_ajeno_responde_404(self):
        for nombre in ["detalle", "editar", "eliminar"]:
            with self.subTest(vista=nombre):
                url = reverse(f"expedientes:{nombre}", args=[self.exp_beto.pk])
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_post_ajeno_no_modifica_nada(self):
        for nombre in ["editar", "eliminar"]:
            with self.subTest(vista=nombre):
                url = reverse(f"expedientes:{nombre}", args=[self.exp_beto.pk])
                respuesta = self.client.post(url, {"caratula": "Hackeado", "estado": "activo"})
                self.assertEqual(respuesta.status_code, 404)
        # Si lo hubieran borrado, refresh_from_db también haría fallar el test.
        self.exp_beto.refresh_from_db()
        self.assertEqual(self.exp_beto.caratula, "Lopez c/ Diaz")

    def test_crear_asigna_el_usuario_logueado_como_titular(self):
        self.client.post(reverse("expedientes:nuevo"), {
            "caratula": "Nuevo c/ Otro",
            "estado": "activo",
            "owner": self.beto.pk,  # intento de asignárselo a otro usuario
        })
        nuevo = Expediente.objects.get(caratula="Nuevo c/ Otro")
        self.assertEqual(nuevo.owner, self.ana)


class NumeroDeExpedienteTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_numero_repetido_del_mismo_usuario_da_error_de_formulario(self):
        respuesta = self.client.post(reverse("expedientes:nuevo"), {
            "caratula": "Otro", "estado": "activo", "numero": "100/2026",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Ya tenés un expediente con ese número.")

    def test_dos_usuarios_pueden_tener_el_mismo_numero(self):
        self.client.post(reverse("expedientes:nuevo"), {
            "caratula": "Otro", "estado": "activo", "numero": "200/2026",
        })
        self.assertTrue(Expediente.objects.filter(owner=self.ana, numero="200/2026").exists())

    def test_se_permiten_varios_expedientes_sin_numero(self):
        for caratula in ["Sin numero 1", "Sin numero 2"]:
            self.client.post(reverse("expedientes:nuevo"), {"caratula": caratula, "estado": "activo"})
        self.assertEqual(Expediente.objects.filter(owner=self.ana, numero__isnull=True).count(), 2)

    def test_editar_sin_cambiar_el_numero_funciona(self):
        respuesta = self.client.post(reverse("expedientes:editar", args=[self.exp_ana.pk]), {
            "caratula": "Gomez c/ Perez (editado)", "estado": "activo", "numero": "100/2026",
        })
        self.assertRedirects(respuesta, self.exp_ana.get_absolute_url())

class MensajesTests(DosUsuariosTestCase):
    def setUp(self):
        self.client.force_login(self.ana)

    def test_crear_muestra_mensaje_de_confirmacion(self):
        respuesta = self.client.post(
            reverse("expedientes:nuevo"),
            {"caratula": "Nuevo", "estado": "activo"},
            follow=True,
        )
        self.assertContains(respuesta, "Expediente creado.")

    def test_editar_muestra_mensaje_de_confirmacion(self):
        respuesta = self.client.post(
            reverse("expedientes:editar", args=[self.exp_ana.pk]),
            {"caratula": "Editado", "estado": "activo"},
            follow=True,
        )
        self.assertContains(respuesta, "Cambios guardados.")
        
    def test_eliminar_muestra_mensaje_de_confirmacion(self):
        respuesta = self.client.post(
            reverse("expedientes:eliminar", args=[self.exp_ana.pk]),
            follow=True,
        )
        self.assertContains(respuesta, "Expediente eliminado.")
