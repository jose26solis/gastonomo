"""Valores que cambian entre maquinas.

Se leen del ambiente para que la misma imagen del codigo corra en la maquina de
cada integrante, en la integracion continua y manana en el servidor, sin editar
ningun archivo.
"""

import os
import warnings
from dataclasses import dataclass
from functools import lru_cache

from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Carga las variables de .env al ambiente del proceso, si el archivo existe.
# Busca hacia arriba desde el directorio de trabajo actual, así que corre
# igual desde la raíz del proyecto o desde src/. En CI no hay .env -el
# archivo está en .gitignore- así que esto no hace nada y las variables
# reales las pone el workflow.
load_dotenv()


@dataclass(frozen=True)
class Configuracion:
    """Configuracion de la aplicacion. Inmutable: se lee una vez al arrancar."""

    nombre_aplicacion: str
    version: str
    url_base_datos: str

    # OAuth2 de Microsoft identity platform (Outlook / Microsoft 365).
    # El segmento de tenant en la URL de autorización tiene que coincidir con
    # el "Supported account types" que se eligió al registrar la app en Azure:
    #   - "common"    → app multi-tenant + cuentas personales (lo que usamos:
    #                   la app puede estar registrada bajo el tenant de una
    #                   universidad u organización, y aun así dejar entrar
    #                   cuentas personales como sabejosoli27@hotmail.com).
    #   - "consumers" → app registrada como "Personal accounts only".
    #   - "organizations" → solo cuentas de una organización, sin personales.
    # Un desajuste entre esto y cómo se registró la app da AADSTS50194 o
    # AADSTS700016 al autorizar.
    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_tenant: str
    microsoft_redirect_uri: str

    # OAuth2 de Google (Gmail).
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # Clave simetrica con la que se cifran los tokens antes de guardarlos.
    clave_cifrado_tokens: str

    # Origenes desde los que el frontend puede llamar a esta API (CORS).
    origenes_permitidos: list[str]

    # Servicio Web de Indicadores Economicos del Banco Central de Costa Rica
    # (tipo de cambio). A diferencia de Outlook/Gmail no es OAuth2: hay que
    # suscribirse una sola vez en https://gee.bccr.fi.cr/Indicadores/Suscripciones/UI/ConsultaIndicadores
    # con un correo, confirmar la suscripcion desde ese correo, y guardar el
    # token que el BCCR genera. Sin estas dos variables, la conversion de
    # moneda simplemente no aparece -el resto de la aplicacion sigue
    # funcionando igual, como con Outlook/Gmail sin configurar.
    bccr_correo: str
    bccr_token: str


@lru_cache
def obtener_configuracion() -> Configuracion:
    """Arma la configuracion desde el ambiente, con valores por defecto de desarrollo.

    Por defecto la base es un archivo SQLite local, para que el proyecto corra
    sin instalar nada y para que la integracion continua -que no levanta
    Docker- siga arrancando la app tal cual. Con 'docker compose up -d
    postgres' corriendo, GASTONOMO_URL_BASE_DATOS en el .env apunta esta misma
    aplicacion a esa base en su lugar; ver la seccion de PostgreSQL del
    README. El esquema lo sigue creando `crear_tablas()` desde los modelos de
    SQLAlchemy -es un esquema propio de la aplicacion, no el que migran las
    migraciones de Flyway de docs/adr/ADR-003, que entregan el modelo de
    dominio original del Laboratorio 2 como un ejercicio aparte.

    Las credenciales de Outlook y Gmail no tienen un valor de desarrollo posible:
    cada integrante tiene que registrar su propia app en Azure y en Google Cloud
    y ponerlas en su `.env`. Sin ellas, todo el resto del sistema sigue
    funcionando; solo fallan los endpoints de vinculacion de correo.
    """
    return Configuracion(
        nombre_aplicacion=os.getenv("GASTONOMO_NOMBRE", "Gastonomo"),
        version=os.getenv("GASTONOMO_VERSION", "0.1.0"),
        url_base_datos=os.getenv("GASTONOMO_URL_BASE_DATOS", "sqlite:///./gastonomo.sqlite3"),
        microsoft_client_id=os.getenv("GASTONOMO_MICROSOFT_CLIENT_ID", ""),
        microsoft_client_secret=os.getenv("GASTONOMO_MICROSOFT_CLIENT_SECRET", ""),
        microsoft_tenant=os.getenv("GASTONOMO_MICROSOFT_TENANT", "common"),
        microsoft_redirect_uri=os.getenv(
            "GASTONOMO_MICROSOFT_REDIRECT_URI",
            "http://localhost:5173/vincular/outlook/callback",
        ),
        google_client_id=os.getenv("GASTONOMO_GOOGLE_CLIENT_ID", ""),
        google_client_secret=os.getenv("GASTONOMO_GOOGLE_CLIENT_SECRET", ""),
        google_redirect_uri=os.getenv(
            "GASTONOMO_GOOGLE_REDIRECT_URI",
            "http://localhost:5173/vincular/gmail/callback",
        ),
        clave_cifrado_tokens=_obtener_clave_cifrado_tokens(),
        origenes_permitidos=_obtener_origenes_permitidos(),
        bccr_correo=os.getenv("GASTONOMO_BCCR_CORREO", ""),
        bccr_token=os.getenv("GASTONOMO_BCCR_TOKEN", ""),
    )


def _obtener_origenes_permitidos() -> list[str]:
    """Lee los orígenes permitidos para CORS, separados por coma.

    El redirect_uri de OAuth apunta al frontend a propósito (ver
    `microsoft_redirect_uri`): es el frontend el que recibe al titular de
    vuelta y llama a esta API por `fetch` para completar la vinculación. Sin
    CORS habilitado hacia ese origen, el navegador bloquearía esa llamada.
    """
    origenes = os.getenv("GASTONOMO_ORIGENES_PERMITIDOS", "http://localhost:5173")
    return [origen.strip() for origen in origenes.split(",") if origen.strip()]


def _obtener_clave_cifrado_tokens() -> str:
    """Lee la clave de cifrado del ambiente, o genera una efimera para desarrollo.

    Una clave generada al vuelo no sirve mas alla de un arranque: al reiniciar
    el proceso cambia, y los tokens que se cifraron con la anterior quedan
    indescifrables (las cuentas de correo tocaria vincularlas de nuevo). Por
    eso se avisa por warning en vez de fallar: es comodo para levantar el
    proyecto la primera vez, pero no es apto para nada que deba sobrevivir un
    reinicio.
    """
    clave = os.getenv("GASTONOMO_CLAVE_CIFRADO_TOKENS")
    if clave:
        return clave
    warnings.warn(
        "GASTONOMO_CLAVE_CIFRADO_TOKENS no esta definida: se genero una clave "
        "temporal valida solo para este arranque. Los tokens de correo cifrados "
        "ahora no se van a poder leer despues de reiniciar. Definila con: "
        'python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"',
        stacklevel=2,
    )
    return Fernet.generate_key().decode()
