"""Doble de prueba de `IdentidadGoogleProveedor`, compartido entre pruebas.

No es un archivo `test_*.py` a propósito: pytest no debe intentar coleccionarlo
como una suite, es solo una pieza que las suites importan.
"""

from app.business.services.identidad_google import PerfilDeGoogle


class IdentidadGoogleFalsa:
    """No toca la red: devuelve un perfil fijo y recuerda qué código le pidieron."""

    def __init__(self, perfil: PerfilDeGoogle | None = None) -> None:
        self.perfil = perfil or PerfilDeGoogle(
            id="google-1", correo="ana@gmail.com", correo_verificado=True, nombre="Ana Pérez"
        )
        self.codigo_recibido: str | None = None

    def url_de_autorizacion(self, estado: str) -> str:
        return f"https://accounts.google.com/falso/autorizar?state={estado}"

    def perfil_desde_codigo(self, codigo: str) -> PerfilDeGoogle:
        self.codigo_recibido = codigo
        return self.perfil
