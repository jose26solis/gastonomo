# Gastonomo · Control de gastos personales por categorías

[![CI](https://github.com/LewMontes/Proyecto-EIF509-Personal/actions/workflows/ci.yml/badge.svg)](https://github.com/LewMontes/Proyecto-EIF509-Personal/actions/workflows/ci.yml)

Sistema web multiusuario donde cualquier persona crea su cuenta, vincula el buzón donde le llegan
sus comprobantes de compra, y el sistema clasifica su gasto por categoría mostrándole en vivo el
avance contra su presupuesto mensual.

**EIF509 Desarrollo de Aplicaciones Basadas en Web · NRC 51092 · Grupo G01 · II Ciclo 2026**
Universidad Nacional · Escuela de Informática y Computación

| |                                                         |
|---|---------------------------------------------------------|
| **Integrante 1** | Luis Antonio Montes de Oca Ruiz · carné 191862          |
| **Integrante 2** | Jose Alexis Solís Carvajal · carné `<COMPLETAR>`        |
| **Entrega actual** | Laboratorio 1 — Arquitectura base y esqueleto por capas |

---

## Stack

**Python 3.14 · FastAPI · SQLAlchemy 2.0 · PostgreSQL · React**

> El curso recomienda Java 21 + Spring Boot 3. Este equipo solicitó y obtuvo autorización del
> profesor para usar un stack alternativo equivalente. La justificación técnica completa —con las
> alternativas descartadas y lo que la decisión nos cuesta— está en
> [ADR-001](docs/adr/ADR-001-eleccion-del-stack.md).

---

## Qué incluye este laboratorio

El Laboratorio 1 entrega **la arquitectura, no el sistema**. Es el esqueleto por capas funcionando
de punta a punta con una sola entidad del dominio (`Categoria`, con `Usuario` como su dueña), para
demostrar la estructura sin adelantar trabajo de los laboratorios siguientes.

El dominio completo —once entidades y dos procesos de negocio— está diseñado y documentado en la
[Propuesta de Dominio](docs/propuesta-dominio.md); se implementa en los laboratorios siguientes.

> **Nota:** por decisión del equipo se adelantó la vinculación de buzones de correo (Outlook y
> Gmail) fuera del orden de los laboratorios, para validar contra un banco real que la ingesta es
> viable. Queda descrita en su propia sección más abajo y no es parte de lo que exige el
> Laboratorio 1.

---

## Cómo correrlo

Necesitás **Python 3.12 o superior** (nosotros usamos 3.14). **No hace falta instalar ninguna base
de datos**: en este laboratorio la aplicación usa SQLite local y crea el archivo sola al arrancar.

### 1. Clonar y crear el entorno virtual

```bash
git clone https://github.com/LewMontes/Proyecto-EIF509-Personal.git
```

```bash
python -m venv .venv
```

Activarlo — en **Windows (PowerShell)**:

```bash
.venv\Scripts\Activate.ps1
```

En **Mac / Linux**:

```bash
source .venv/bin/activate
```

### 2. Instalar las dependencias

```bash
pip install -e ".[dev]"
```

### 3. Levantar la aplicación

```bash
uvicorn app.main:app --reload --app-dir src
```

### 4. Probarla

Con la app corriendo, en otra terminal:

```bash
curl http://localhost:8000/api/salud
```

Respuesta esperada:

```json
{"estado":"OK - sistema en linea","aplicacion":"Gastonomo","version":"0.1.0"}
```

La documentación interactiva de la API se genera sola. Abrila en el navegador:

- **Swagger UI** → http://localhost:8000/docs
- **ReDoc** → http://localhost:8000/redoc

### Endpoints disponibles

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/salud` | Confirma que el sistema está en línea |
| `POST` | `/api/categorias` | Crea una categoría aplicando las reglas del dominio |
| `GET` | `/api/categorias?usuario_id=1` | Lista las categorías activas de un usuario |
| `GET` | `/api/cuentas-correo/outlook/iniciar?usuario_id=1` | Da la URL para vincular un buzón de Outlook |
| `GET` | `/api/cuentas-correo/gmail/iniciar?usuario_id=1` | Da la URL para vincular un buzón de Gmail |
| `GET` | `/api/cuentas-correo?usuario_id=1` | Lista los buzones vinculados de un usuario |
| `GET` | `/api/cuentas-correo/{id}/probar?usuario_id=1` | Trae los últimos mensajes, para confirmar que el token sirve |
| `DELETE` | `/api/cuentas-correo/{id}?usuario_id=1` | Desvincula un buzón |

Los tres primeros no necesitan nada extra. Los de `/api/cuentas-correo` sí requieren credenciales
de Microsoft/Google — ver la sección **Vinculación de correo** más abajo.

### 5. Correr las pruebas y el linter

```bash
pytest -v
```

```bash
ruff check . && ruff format --check .
```

Son los mismos comandos que ejecuta la integración continua. Las pruebas corren contra una base
SQLite **en memoria**, así que no tocan ningún archivo ni necesitan infraestructura.

---

## Cómo está organizado

Arquitectura en tres capas más configuración. La regla de oro:
**presentación → negocio → datos, nunca al revés.**

```
src/app/
├── presentation/   → Habla HTTP. Recibe JSON, llama al servicio, devuelve JSON.
│   ├── routers/        salud.py · categorias.py · cuentas_correo.py
│   ├── schemas.py      DTOs de entrada y salida
│   └── dependencies.py arma los servicios con sus repositorios
│
├── business/       → Reglas del negocio. No sabe que existe HTTP.
│   ├── services/        categoria_service.py · cuenta_correo_service.py
│   │   └── correo/      proveedor.py · outlook.py · gmail.py (hablan con Microsoft/Google)
│   ├── parsers/          comprobante_bac.py (lee notificaciones de BAC con regex)
│   ├── seguridad/        cifrado.py (cifra los tokens antes de guardarlos)
│   └── errors.py        violaciones de reglas del dominio
│
├── data/           → Entidades y consultas. No contiene reglas de negocio.
│   ├── models/          usuario.py · categoria.py · cuenta_correo.py · base.py · enums.py · tipos.py
│   └── repositories/    el único lugar del sistema que consulta datos
│
├── config/         → Lo que cambia entre máquinas.
│   ├── settings.py      nombre, versión, URL de la base, credenciales OAuth
│   ├── database.py      motor, sesión y creación de tablas
│   └── cliente_http.py  cliente HTTP compartido hacia Microsoft/Google
│
└── main.py         → Arma la app, CORS, y traduce errores de negocio a códigos HTTP.
```

El frontend vive aparte, en [`frontend/`](frontend/) — ver la sección de abajo.

Tres decisiones sostienen la separación, ya que Python no la impone por sí solo:

1. El servicio recibe una **dataclass propia** (`CrearCategoriaComando`), no un modelo de FastAPI.
2. El repositorio **nunca confirma la transacción**: el `commit` lo hace el servicio, que es el
   único que sabe si la operación de negocio completa terminó bien.
3. Los errores de negocio son **excepciones propias** sin ninguna referencia a HTTP; `main.py` es
   el único archivo que las traduce a códigos de respuesta.

---

## Vinculación de correo (Outlook y Gmail)

El sistema puede vincular un buzón de Outlook o de Gmail vía OAuth2 y, una vez vinculado, leer sus
mensajes recientes para confirmar que el token sirve. Es la base del Proceso 2 de ingesta de
comprobantes, descrito en la [Propuesta de Dominio](docs/propuesta-dominio.md); el parseo del
comprobante en sí ya está resuelto y probado contra una notificación real de BAC en
[`business/parsers/comprobante_bac.py`](src/app/business/parsers/comprobante_bac.py), pero
todavía no está conectado al flujo de vinculación.

### Por qué el frontend es dueño del `redirect_uri`

Microsoft y Google devuelven al titular, tras autorizar, a una URL que **nosotros** registramos de
antemano. Esa URL apunta al frontend (`http://localhost:5173/vincular/outlook/callback`), no al
backend: así el navegador nunca aterriza en un JSON crudo. El frontend lee `code` y `state` de la
URL y se los pasa al backend por `fetch` — ahí sí se completa la vinculación. El `state` no
necesita una sesión de servidor: es el `usuario_id` cifrado con la misma clave de los tokens, así
que el backend lo descifra sin tener que recordar nada entre la ida y la vuelta.

### Registrar las apps (una sola vez, por integrante)

**Azure AD / Entra ID (Outlook):**

1. https://portal.azure.com → *Microsoft Entra ID* → *App registrations* → *New registration*.
2. Nombre `Gastonomo`. **Supported account types**: *Personal Microsoft accounts only*.
3. Redirect URI tipo *Web*: `http://localhost:5173/vincular/outlook/callback`.
4. *Certificates & secrets* → *New client secret* → copiar el valor (solo se ve una vez).
5. *API permissions* → *Add a permission* → *Microsoft Graph* → *Delegated* → `Mail.Read`,
   `User.Read`, `offline_access`.

**Google Cloud (Gmail):**

1. https://console.cloud.google.com → crear proyecto → *APIs & Services* → *Library* → habilitar
   **Gmail API**.
2. *OAuth consent screen*: tipo *External*, agregarte como *Test user*.
3. *Credentials* → *Create credentials* → *OAuth client ID* → tipo *Web application*.
4. Redirect URI: `http://localhost:5173/vincular/gmail/callback`.

### Configurar el backend

Crear un archivo `.env` en la raíz del proyecto (no se sube: está en `.gitignore`) o exportar las
variables antes de levantar `uvicorn`:

```bash
GASTONOMO_MICROSOFT_CLIENT_ID=<el client id de Azure>
GASTONOMO_MICROSOFT_CLIENT_SECRET=<el secreto de Azure>
GASTONOMO_GOOGLE_CLIENT_ID=<el client id de Google>
GASTONOMO_GOOGLE_CLIENT_SECRET=<el secreto de Google>
GASTONOMO_CLAVE_CIFRADO_TOKENS=<ver el comando de abajo>
```

La clave de cifrado protege los tokens guardados en la base. Sin ella el sistema arranca igual con
una clave temporal, pero avisa por warning y los tokens no sobreviven un reinicio:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Los valores por defecto de `microsoft_redirect_uri`, `google_redirect_uri` y CORS ya apuntan al
frontend en `http://localhost:5173`; solo hay que tocarlos si se corre en otro puerto o dominio.

### Correr el frontend

```bash
cd frontend
npm install
npm run dev
```

Abre en `http://localhost:5173`. Deja poner un `usuario_id` (por ahora no hay login: el
Laboratorio 1 siembra el usuario de demostración con id `1`), vincular Outlook o Gmail, ver los
buzones vinculados, probar la conexión trayendo sus últimos mensajes, y desvincular.

Sin credenciales configuradas, el botón de conectar igual redirige a Microsoft/Google real, que
rechaza la solicitud con un error legible (`unauthorized_client`) — es la forma de confirmar que
el flujo está bien armado antes de tener las credenciales a mano.

---

## Documentación

| Documento | Qué contiene |
|---|---|
| [Propuesta de Dominio](docs/propuesta-dominio.md) | El negocio, los actores, las 11 entidades y los 2 procesos con sus reglas, cálculos y validaciones. |
| [Arquitectura](docs/arquitectura.md) | Diagramas de capas, recorrido de una petición, modelo entidad-relación y despliegue previsto. |
| [ADR-001 · Elección del stack](docs/adr/ADR-001-eleccion-del-stack.md) | Por qué Python + FastAPI + PostgreSQL + React, qué descartamos y qué nos cuesta. |

---

## Integración continua

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) corre en cada push y en cada pull request
sobre `main` y `master`. Instala el proyecto en una máquina limpia, revisa el código con `ruff`,
ejecuta la suite de pruebas y **levanta el servidor de verdad** para confirmar que `/api/salud`
responde.

El estado se ve en la pestaña **Actions** del repositorio y en la insignia del inicio de este
README.

---

## Estado del proyecto

El curso son siete laboratorios incrementales sobre esta misma base. Todavía no sabemos el
contenido exacto de cada uno, así que lo pendiente queda listado sin asignarle número.

- [x] **Laboratorio 1** *(entregado)* — Arquitectura por capas, `Usuario` y `Categoria`, propuesta de dominio, CI
- [x] **Vinculación OAuth2 de buzones** *(adelantado, fuera de orden)* — Outlook y Gmail, backend y
      primera pantalla de frontend. Ver [Vinculación de correo](#vinculación-de-correo-outlook-y-gmail).
- [x] **Parser de comprobantes de BAC** *(adelantado)* — probado contra una notificación real,
      confianza 1.0 en los ocho campos. [`comprobante_bac.py`](src/app/business/parsers/comprobante_bac.py)

Pendiente para los laboratorios siguientes:

- [ ] PostgreSQL con migraciones y las nueve entidades restantes del dominio
- [ ] Resto del frontend React: catálogo de categorías, compras, presupuestos con avance en vivo
- [ ] Proceso transaccional de ingesta: conectar el parser de BAC (y sumar otros bancos) a las
      cuentas ya vinculadas, con conciliación y actualización de presupuesto
- [ ] Autenticación y roles (titular, administrador)
