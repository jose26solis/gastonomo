"""Errores del dominio.

Ninguno menciona HTTP a proposito: `main.py` es el unico archivo autorizado a
traducirlos a codigos de respuesta. Asi el mismo servicio se puede llamar desde
un script o una tarea programada sin arrastrar el protocolo.
"""


class ErrorDeNegocio(Exception):
    """Raiz de todos los errores del dominio."""


class DatosInvalidos(ErrorDeNegocio):
    """El dato entra con la forma correcta pero no cumple una regla del dominio."""


class RecursoNoEncontrado(ErrorDeNegocio):
    """Se referencio algo que no existe o que no pertenece al titular."""


class ReglaDeNegocioViolada(ErrorDeNegocio):
    """La operacion choca con el estado actual del sistema."""


class CredencialesInvalidas(ErrorDeNegocio):
    """El correo/contraseña no calzan, o la sesión no es válida o venció.

    Un solo tipo de error para "no existe ese correo" y "la contraseña está
    mal" a propósito: distinguirlos en la respuesta le confirmaría a quien
    ataque que un correo puntual sí tiene cuenta en el sistema.
    """


class AccesoDenegado(ErrorDeNegocio):
    """El titular autenticado no es dueño del recurso que pidió.

    Distinto de `RecursoNoEncontrado`: acá el recurso existe y el request
    está bien formado, pero pertenece a otra persona. Se traduce a 403, no a
    404 -confirmar que algo existe pero no es tuyo es lo que se quiere decir,
    no fingir que no existe.
    """


class ErrorDeProveedorExterno(ErrorDeNegocio):
    """Un servicio externo (Microsoft, Google, el Banco Central) rechazo la solicitud, o no
    respondio.

    No es un error de nuestras reglas: el dato pedido era correcto, pero el
    proveedor -el codigo de autorizacion vencio, el token se revoco, la red
    fallo- no lo pudo resolver. Se distingue del resto para que `main.py` la
    traduzca a 502 en vez de a un 4xx que sugeriria que el cliente se equivoco.
    """
