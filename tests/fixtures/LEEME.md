# Muestras de comprobantes

Cada archivo de esta carpeta es un comprobante **anonimizado**: se conservan el formato,
las etiquetas y la puntuacion exactas del banco, pero el nombre del titular, el correo,
los ultimos cuatro digitos y los numeros de autorizacion y referencia estan cambiados.

Nunca subir a este repositorio un comprobante real sin anonimizar: el repositorio es
publico y esos campos identifican a una persona y a su tarjeta.

El signo `?` que aparece dentro de las palabras acentuadas no es un error de captura.
Es lo que devuelve la extraccion de texto cuando el comprobante viene de un correo
impreso a PDF desde el navegador: la fuente incrustada pierde el mapa de los acentos.
El parser tiene que tolerarlo, y por eso la muestra lo conserva tal cual.
