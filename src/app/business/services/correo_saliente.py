"""Correo saliente del propio servidor -no confundir con los buzones vinculados
que `cuenta_correo_service.py` lee (esos son del titular; este lo manda Gastonomo).

Hoy el único flujo que necesita escribirle a alguien es "Recuperar contraseña"
(`AuthService.solicitar_recuperacion_contrasena`), pero el servicio queda
aparte y sin ninguna noción de contraseñas -si mañana hace falta otro correo
saliente (una notificación de presupuesto excedido, por ejemplo), ya está listo.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config.settings import Configuracion

logger = logging.getLogger(__name__)


class EnviarCorreoService:
    """Manda un correo por SMTP, o lo loguea si no hay servidor configurado.

    Un servidor SMTP real -igual que las credenciales de Outlook/Gmail o la
    suscripción del BCCR- es algo que cada integrante tiene que traer con lo
    suyo; no hay valor de desarrollo posible. Sin `smtp_host`, el resto del
    flujo de recuperación de contraseña sigue funcionando igual: el enlace
    queda en el log del servidor en vez de en una bandeja de entrada, y de
    ahí lo copia quien esté probando.
    """

    def __init__(self, configuracion: Configuracion) -> None:
        self._configuracion = configuracion

    def enviar(self, destinatario: str, asunto: str, cuerpo: str) -> None:
        if not self._configuracion.smtp_host:
            logger.warning(
                "SMTP no configurado (GASTONOMO_SMTP_HOST vacío) -no se envía correo de "
                "verdad. Para %s, asunto %r:\n%s",
                destinatario,
                asunto,
                cuerpo,
            )
            return

        mensaje = EmailMessage()
        mensaje["Subject"] = asunto
        mensaje["From"] = self._configuracion.smtp_remitente or self._configuracion.smtp_usuario
        mensaje["To"] = destinatario
        mensaje.set_content(cuerpo)

        with smtplib.SMTP(self._configuracion.smtp_host, self._configuracion.smtp_puerto) as smtp:
            smtp.starttls()
            if self._configuracion.smtp_usuario:
                smtp.login(self._configuracion.smtp_usuario, self._configuracion.smtp_contrasena)
            smtp.send_message(mensaje)
