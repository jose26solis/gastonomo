"""Tipo de cambio de referencia (colones/dólares), vía el Banco Central de Costa Rica.

Habla con el "Servicio Web de Indicadores Económicos" del BCCR
(https://gee.bccr.fi.cr/Indicadores/Suscripciones/WS/wsindicadoreseconomicos.asmx),
un servicio SOAP/ASMX clásico que también acepta invocación por HTTP GET.
Igual que Outlook y Gmail hace falta una suscripción propia -acá no es
OAuth2, es un correo y un token que el BCCR entrega al confirmar la
suscripción, gratis y sin costo (ver GASTONOMO_BCCR_CORREO/TOKEN en
`settings.py` y la sección de conversión de moneda del README).

Nota de implementación: el BCCR describe sus parámetros por función en la
documentación pública ("código del indicador", "correo electrónico"...),
no publica los nombres literales que espera el lado HTTP. Los nombres
usados acá -tcIndicador, tcFechaInicio, tcFechaFinal, tcNombre,
tnSubNiveles- están confirmados contra una integración real en
producción; tcCorreo y tcToken siguen el mismo patrón de nombres pero no
se pudieron confirmar en vivo -el servicio del BCCR estaba caído al
escribir esto. Si el BCCR devuelve un error de parámetro con credenciales
reales ya configuradas, es el primer lugar donde mirar.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

import httpx

from app.business.errors import ErrorDeProveedorExterno
from app.config.settings import Configuracion

_URL_SERVICIO = (
    "https://gee.bccr.fi.cr/Indicadores/Suscripciones/WS/wsindicadoreseconomicos.asmx"
    "/ObtenerIndicadoresEconomicosXML"
)
_INDICADOR_COMPRA = 317
_INDICADOR_VENTA = 318
_DIAS_DE_MARGEN = 7  # cubre un fin de semana largo o feriado sin dato publicado


@dataclass(frozen=True)
class TipoDeCambio:
    """Tipo de cambio de referencia del colón contra el dólar, para un día."""

    fecha: date
    compra: Decimal
    venta: Decimal


class TipoCambioService:
    """Consulta el tipo de cambio de referencia del BCCR, con caché en memoria por fecha.

    El tipo de cambio no cambia dentro del mismo día -el BCCR publica el
    del día siguiente después de las 5:30pm-, así que pedirlo de nuevo
    para la misma fecha no debería volver a tocar la red. La caché es de
    proceso, no de base de datos: es información pública y de referencia,
    no algo que valga la pena persistir por usuario.
    """

    def __init__(self, cliente: httpx.Client, configuracion: Configuracion) -> None:
        self._cliente = cliente
        self._correo = configuracion.bccr_correo
        self._token = configuracion.bccr_token
        self._cache: dict[date, TipoDeCambio] = {}

    @property
    def configurado(self) -> bool:
        """Si hay credenciales del BCCR -sin ellas, no tiene sentido intentar la llamada."""
        return bool(self._correo and self._token)

    def obtener(self, fecha: date | None = None) -> TipoDeCambio:
        """El tipo de cambio de referencia más reciente hasta la fecha pedida (hoy, por defecto).

        Consulta un rango de `_DIAS_DE_MARGEN` días terminando en la fecha
        pedida y se queda con el valor más reciente: el BCCR no publica
        tipo de cambio los fines de semana ni los feriados, así que pedir
        exactamente un sábado daría "Nothing" si se consultara un solo día.
        """
        if not self.configurado:
            raise ErrorDeProveedorExterno(
                "El tipo de cambio no está configurado: falta GASTONOMO_BCCR_CORREO y/o "
                "GASTONOMO_BCCR_TOKEN. Ver la sección de conversión de moneda del README "
                "para suscribirse al servicio del Banco Central."
            )
        fecha = fecha or date.today()
        if fecha in self._cache:
            return self._cache[fecha]

        desde = fecha - timedelta(days=_DIAS_DE_MARGEN)
        compra = self._ultimo_valor(_INDICADOR_COMPRA, desde, fecha)
        venta = self._ultimo_valor(_INDICADOR_VENTA, desde, fecha)
        resultado = TipoDeCambio(fecha=fecha, compra=compra, venta=venta)
        self._cache[fecha] = resultado
        return resultado

    def _ultimo_valor(self, indicador: int, desde: date, hasta: date) -> Decimal:
        respuesta = self._cliente.get(
            _URL_SERVICIO,
            params={
                "tcIndicador": indicador,
                "tcFechaInicio": desde.strftime("%d/%m/%Y"),
                "tcFechaFinal": hasta.strftime("%d/%m/%Y"),
                "tcNombre": "Gastonomo",
                "tnSubNiveles": "N",
                "tcCorreo": self._correo,
                "tcToken": self._token,
            },
        )
        if respuesta.status_code >= 400:
            raise ErrorDeProveedorExterno(
                f"El Banco Central rechazó la solicitud de tipo de cambio "
                f"(HTTP {respuesta.status_code}): {respuesta.text[:300]}"
            )
        return self._valor_mas_reciente(respuesta.text)

    def _valor_mas_reciente(self, xml_crudo: str) -> Decimal:
        try:
            raiz = ElementTree.fromstring(xml_crudo)
        except ElementTree.ParseError as error:
            raise ErrorDeProveedorExterno(
                "El Banco Central devolvió una respuesta que no se pudo leer como XML."
            ) from error

        # Invocado por HTTP GET (no SOAP puro), ObtenerIndicadoresEconomicosXML
        # puede anidar el XML de verdad como texto escapado dentro de un
        # elemento contenedor. Si el primer parseo no encuentra nada, se
        # reintenta con el texto interno como un segundo documento XML.
        valores = raiz.findall(".//NUM_VALOR")
        if not valores and raiz.text and "<" in raiz.text:
            try:
                interior = ElementTree.fromstring(raiz.text)
                valores = interior.findall(".//NUM_VALOR")
            except ElementTree.ParseError:
                valores = []

        if not valores or not valores[-1].text:
            raise ErrorDeProveedorExterno(
                "El Banco Central no devolvió ningún valor de tipo de cambio para ese rango "
                "de fechas -puede que el rango consultado no tenga ningún día hábil."
            )
        try:
            return Decimal(valores[-1].text.strip())
        except InvalidOperation as error:
            raise ErrorDeProveedorExterno(
                f"El Banco Central devolvió un valor de tipo de cambio no numérico: "
                f"{valores[-1].text!r}"
            ) from error
