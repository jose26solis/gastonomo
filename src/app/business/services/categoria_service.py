"""Reglas de negocio de las categorias."""

import re
from dataclasses import dataclass

from app.business.errors import DatosInvalidos, RecursoNoEncontrado, ReglaDeNegocioViolada
from app.data.models.categoria import Categoria
from app.data.repositories.categoria_repository import CategoriaRepository
from app.data.repositories.usuario_repository import UsuarioRepository

LARGO_MAXIMO_NOMBRE = 60
PATRON_COLOR_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True)
class CrearCategoriaComando:
    """Orden que recibe el negocio para crear una categoria.

    Es una dataclass propia y no un modelo de Pydantic a proposito: si el
    servicio recibiera modelos de FastAPI, el negocio quedaria amarrado a la
    forma de la API y no se podria reutilizar desde otro punto de entrada.
    """

    usuario_id: int
    nombre: str
    color_hex: str
    descripcion: str | None = None
    categoria_padre_id: int | None = None


class CategoriaService:
    """Aplica las reglas del dominio y decide cuando confirmar la transaccion."""

    def __init__(
        self,
        categoria_repository: CategoriaRepository,
        usuario_repository: UsuarioRepository,
    ) -> None:
        self.categorias = categoria_repository
        self.usuarios = usuario_repository

    def crear(self, comando: CrearCategoriaComando) -> Categoria:
        """Crea una categoria de un usuario.

        Reglas que aplica:
        - El nombre no puede venir vacio ni pasar de 60 caracteres.
        - El color debe ser hexadecimal (#RRGGBB): lo consumen los graficos.
        - El titular debe existir y estar activo.
        - No puede repetirse el nombre dentro de la misma cuenta.
        - La categoria padre debe existir, estar activa y ser del mismo titular.
        - Colgarle una hija a una categoria la convierte en categoria padre, y
          las padre dejan de recibir gasto directo: pasan a totalizar.
        """
        nombre = comando.nombre.strip()
        if not nombre:
            raise DatosInvalidos("El nombre de la categoria no puede venir vacio.")
        if len(nombre) > LARGO_MAXIMO_NOMBRE:
            raise DatosInvalidos(
                f"El nombre de la categoria no puede pasar de {LARGO_MAXIMO_NOMBRE} caracteres."
            )
        if not PATRON_COLOR_HEX.match(comando.color_hex):
            raise DatosInvalidos(
                f"El color '{comando.color_hex}' no es hexadecimal valido. Se espera #RRGGBB."
            )

        self._asegurar_usuario_activo(comando.usuario_id)

        if self.categorias.buscar_por_nombre(comando.usuario_id, nombre) is not None:
            raise ReglaDeNegocioViolada(f"Ya existe una categoria llamada '{nombre}' en la cuenta.")

        categoria_padre = None
        if comando.categoria_padre_id is not None:
            categoria_padre = self.categorias.obtener_de_usuario(
                comando.categoria_padre_id, comando.usuario_id
            )
            if categoria_padre is None:
                raise RecursoNoEncontrado(
                    f"La categoria padre {comando.categoria_padre_id} no existe en esta cuenta."
                )
            if not categoria_padre.activa:
                raise ReglaDeNegocioViolada(
                    f"La categoria padre '{categoria_padre.nombre}' esta desactivada."
                )
            categoria_padre.es_hoja = False

        categoria = Categoria(
            usuario_id=comando.usuario_id,
            nombre=nombre,
            descripcion=comando.descripcion,
            color_hex=comando.color_hex.upper(),
            categoria_padre_id=comando.categoria_padre_id,
            es_hoja=True,
            activa=True,
        )
        self.categorias.agregar(categoria)

        # El commit vive aqui, no en el repositorio: este es el unico punto que
        # sabe que la operacion completa -incluido el cambio en la padre- cuadro.
        self.categorias.sesion.commit()
        return categoria

    def listar_activas(self, usuario_id: int) -> list[Categoria]:
        """Lista las categorias activas de un usuario."""
        self._asegurar_usuario_activo(usuario_id)
        return self.categorias.listar_activas_de_usuario(usuario_id)

    def _asegurar_usuario_activo(self, usuario_id: int) -> None:
        usuario = self.usuarios.obtener_por_id(usuario_id)
        if usuario is None:
            raise RecursoNoEncontrado(f"El usuario {usuario_id} no existe.")
        if not usuario.activo:
            raise ReglaDeNegocioViolada(f"El usuario {usuario_id} esta desactivado.")
