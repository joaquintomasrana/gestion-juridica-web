from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView

# Nombre de la cookie que guarda el tema elegido, y sus dos valores posibles.
COOKIE_TEMA = "tema"
TEMA_CLARO = "claro"
TEMA_OSCURO = "oscuro"
UN_ANIO = 365 * 24 * 60 * 60  # en segundos


class RegistroView(CreateView):
    form_class = UserCreationForm
    template_name = "registration/registro.html"
    success_url = reverse_lazy("login")


class CambiarTemaView(View):
    """Alterna entre modo claro y oscuro, sin JavaScript.

    El botón del encabezado es un formulario POST (con CSRF): esta vista guarda
    la elección en una cookie y vuelve a la página donde estaba el usuario.
    No exige sesión: el modo oscuro también se puede usar en el login.
    Solo acepta POST (un GET responde 405), como toda acción que cambia algo.
    """

    def post(self, request):
        actual = request.COOKIES.get(COOKIE_TEMA, TEMA_CLARO)
        nuevo = TEMA_CLARO if actual == TEMA_OSCURO else TEMA_OSCURO

        # "volver" lo manda el formulario, así que se valida: solo se redirige a
        # una dirección de este mismo sitio. Si no, sería una "redirección
        # abierta" (un link nuestro que lleve a un sitio falso).
        volver = request.POST.get("volver", "")
        if not url_has_allowed_host_and_scheme(
            volver, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            volver = "expedientes:inicio"   # redirect() también acepta el nombre de una ruta

        respuesta = redirect(volver)
        respuesta.set_cookie(
            COOKIE_TEMA,
            nuevo,
            max_age=UN_ANIO,
            samesite="Lax",
            secure=request.is_secure(),  # en producción (HTTPS), solo viaja cifrada
            httponly=True,               # la lee el servidor; ningún script la necesita
        )
        return respuesta
