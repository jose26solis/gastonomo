"""Hash y verificación de contraseñas de login.

Con bcrypt, no bruto (SHA-256 sobre la contraseña): un hash de propósito
general se calcula en microsegundos, así que probar millones de contraseñas
robadas de otra fuga contra estos hashes sería trivial. bcrypt es
deliberadamente lento -tiene un factor de costo incrustado en el propio
hash- y la sal va incluida en el resultado, así que no hay que guardarla
aparte ni gestionar ningún parámetro a mano.
"""

import bcrypt

# 12 es el valor por defecto de la librería y el mínimo recomendado hoy; cada
# +1 duplica el costo de calcular un hash (y de que alguien intente adivinar
# uno). Subirlo demasiado en un servidor sin GPU dedicada haría el login
# perceptiblemente lento para el titular real, no solo para quien ataque.
_COSTO = 12


def hashear_contrasena(contrasena: str) -> str:
    """Hashea una contraseña en claro para guardarla. Nunca se guarda la contraseña misma."""
    sal = bcrypt.gensalt(rounds=_COSTO)
    return bcrypt.hashpw(contrasena.encode("utf-8"), sal).decode("ascii")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    """Compara una contraseña en claro contra el hash guardado, en tiempo constante.

    `bcrypt.checkpw` compara en tiempo constante a propósito: un `==` normal
    sobre los hashes se detiene en el primer byte distinto, y esa diferencia
    de tiempo -mínima, pero medible- es suficiente para que un atacante con
    muchos intentos reconstruya el hash byte a byte.
    """
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        # hash_guardado no tiene la forma de un hash de bcrypt -pasa con el
        # usuario de demostración de instalaciones viejas, antes de que este
        # laboratorio existiera. No es una contraseña que pueda "calzar".
        return False
