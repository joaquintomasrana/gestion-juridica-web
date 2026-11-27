from .views import COOKIE_TEMA, TEMA_OSCURO


def tema(request):
    """Pone el tema elegido (claro u oscuro) a disposición de TODAS las plantillas.

    Un "context processor" es una función que Django ejecuta en cada página:
    lo que devuelve se suma al contexto de la plantilla. Así base.html sabe con
    qué colores dibujar la página, sin que cada vista tenga que pasarlo.
    Cualquier valor de la cookie que no sea "oscuro" se trata como claro.
    """
    oscuro = request.COOKIES.get(COOKIE_TEMA) == TEMA_OSCURO
    return {"modo_oscuro": oscuro}
