# Gastonomo · Control de gastos personales por categorías

[![CI](https://github.com/LewMontes/Proyecto-EIF509-Personal/actions/workflows/ci.yml/badge.svg)](https://github.com/LewMontes/Proyecto-EIF509-Personal/actions/workflows/ci.yml)

Sistema web multiusuario donde cualquier persona crea su cuenta, vincula el buzón donde le llegan
sus comprobantes de compra, y el sistema clasifica su gasto por categoría mostrándole en vivo el
avance contra su presupuesto mensual.

**EIF509 Desarrollo de Aplicaciones Basadas en Web · II Ciclo 2026**
Universidad Nacional · Escuela de Informática y Computación

| |                                                         |
|---|---------------------------------------------------------|
| **Integrantes** | Jose Alexis Solís Carvajal · 1-1623-0238          |
|  |    Luis Antonio Montes de Oca Ruiz · 1-1800-0270     |
| **Entrega actual** | Laboratorio 2 — La capa de datos completa: PostgreSQL + MongoDB |

---

## Stack

**Python 3.14 · FastAPI · SQLAlchemy 2.0 · PostgreSQL · MongoDB · React**

> El curso recomienda Java 21 + Spring Boot 3. Este equipo solicitó y obtuvo autorización del
> profesor para usar un stack alternativo equivalente. La justificación técnica completa —con las
> alternativas descartadas y lo que la decisión nos cuesta— está en
> [ADR-001](docs/adr/ADR-001-eleccion-del-stack.md).

---

## Qué incluye este laboratorio

El **Laboratorio 2** entrega **la capa de datos completa**, con persistencia políglota:

| Entregable | Dónde está |
|---|---|
| Esquema PostgreSQL en 3FN con migraciones Flyway `V1`…`V5`, restricciones e índices justificados | [`db/postgres/migrations/`](db/postgres/migrations/) |
| Subdominio en MongoDB: la colección `bitacora_compras`, con la decisión de incrustar justificada | [`db/mongo/init/`](db/mongo/init/) · [ADR-002](docs/adr/ADR-002-subdominio-documental-en-mongodb.md) |
| Datos de ejemplo realistas en las dos bases | [`db/postgres/seeds/`](db/postgres/seeds/) · [`db/mongo/init/02_datos_de_ejemplo.js`](db/mongo/init/02_datos_de_ejemplo.js) |
| Docker Compose que levanta PostgreSQL y MongoDB con un solo comando (`--profile flyway`, ver más abajo) | [`docker-compose.yml`](docker-compose.yml) |
| Documento técnico del modelo y las decisiones de diseño | [Modelo de datos](docs/modelo-de-datos.md) |

En números: **12 tablas · 17 llaves foráneas · 17 restricciones `UNIQUE` · 42 `CHECK` · 46 índices**
en PostgreSQL, más **1 colección con validador de esquema y 4 índices** en MongoDB.

El **Laboratorio 1**, que sigue en el repositorio, entregó la arquitectura por capas funcionando de
punta a punta con dos entidades (`Usuario` y `Categoria`) sobre SQLite. La aplicación **todavía usa
SQLite**: conectarla a estas dos bases es trabajo de un laboratorio siguiente.

El dominio completo está diseñado y documentado en la
[Propuesta de Dominio](docs/propuesta-dominio.md).

> **Nota:** por decisión del equipo se adelantó, fuera del orden de los laboratorios, todo el
> Proceso 2 del dominio sobre la base SQLite actual: vinculación de correo, lectura y clasificación
> de comprobantes reales de BAC, presupuestos con estado en vivo, reportes exportables y el
> frontend completo. Se hizo para validar contra un banco real -no contra datos inventados- que
> todo el recorrido de punta a punta funciona. Queda descrito en la sección
> [Funcionalidades adelantadas](#funcionalidades-adelantadas-clasificación-presupuestos-y-reportes)
> más abajo y no es parte de lo que exige el Laboratorio 2.

---

## Cómo levantar las bases de datos

Necesitás **Docker Desktop**. Desde la raíz del repositorio:

```bash
docker compose up -d
```

Eso levanta PostgreSQL y MongoDB -sin Flyway. No hay que configurar nada más: las credenciales de
desarrollo vienen como valores por defecto (para cambiarlas, copiá `.env.ejemplo` a `.env`).

> **Por qué Flyway queda afuera de este comando:** migra el modelo original de la propuesta de
> dominio (`db/postgres/migrations/`) sobre el mismo PostgreSQL que usa la aplicación en ejecución
> -y sus tablas chocan por nombre con las que la aplicación crea sola (ver
> [Conectarla a PostgreSQL](#conectarla-a-postgresql-en-vez-de-sqlite)). Para levantar el
> Laboratorio 2 tal como se entregó, en un volumen limpio y aparte del que usa la aplicación:
>
> ```bash
> docker compose down -v            # si tenías Postgres con el esquema de la aplicación
> docker compose --profile flyway up -d
> ```
>
> Eso sí aplica las cinco migraciones con sus datos de ejemplo, y levanta MongoDB con la colección
> `bitacora_compras` creada, validada, indexada y sembrada.

Comprobá que todo quedó arriba:

```bash
docker compose ps -a
```

`gastonomo-postgres` y `gastonomo-mongo` deben decir `Up (healthy)`. Si además levantaste el
perfil `flyway`, `gastonomo-flyway` debe decir `Exited (0)`: es una tarea que migra y se apaga, no
un servicio.

Mirá los datos de PostgreSQL:

```bash
docker compose exec postgres psql -U gastonomo -d gastonomo -c "\dt"
```

Y los de MongoDB:

```bash
docker compose exec mongo mongosh --quiet -u gastonomo -p gastonomo_local --authenticationDatabase admin gastonomo --eval "db.bitacora_compras.findOne({compra_id: NumberLong(7)})"
```

Para borrar todo y empezar de cero:

```bash
docker compose down -v
```

### Comprobar que las restricciones hacen su trabajo

Doce intentos de meter datos que el dominio prohíbe. Los doce deben salir como `RECHAZADO OK`:

```bash
docker compose exec -T postgres psql -U gastonomo -d gastonomo -q < db/pruebas/restricciones_postgres.sql
```

Seis intentos contra el validador de MongoDB, más las consultas que justifican el diseño de la
colección:

```bash
docker compose exec -T mongo mongosh --quiet -u gastonomo -p gastonomo_local --authenticationDatabase admin gastonomo < db/pruebas/validador_mongo.js
```

---

## Funcionalidades adelantadas: clasificación, presupuestos y reportes

Todo esto corre hoy sobre la base SQLite del Laboratorio 1, contra correo real de BAC Credomatic
-no contra datos de ejemplo-, y es la parte del sistema que va más allá de lo que exige el
Laboratorio 2:

| Funcionalidad | Qué hace | Dónde está |
|---|---|---|
| Resumen financiero | Lee los comprobantes reales de BAC de un buzón vinculado y los suma por mes y moneda, sin mezclar monedas | [`resumen_service.py`](src/app/business/services/resumen_service.py) |
| Comercios y categorías | Normaliza el nombre del comercio, sugiere su categoría según lo que ese usuario ya clasificó antes (por usuario, no global) y deja confirmar o corregir | [`comercio_service.py`](src/app/business/services/comercio_service.py) |
| Presupuestos | Límite mensual por categoría; el consumo se calcula en vivo contra el gasto real de ese mismo período (`EN_RANGO` / `CERCA_DEL_LIMITE` / `EXCEDIDO`), nunca se guarda como un número aparte | [`presupuesto_service.py`](src/app/business/services/presupuesto_service.py) |
| Reportes exportables | Movimientos en CSV y Excel, resumen del mes más reciente en PDF | [`reportes.py`](src/app/presentation/routers/reportes.py) |
| Frontend completo | Siete pantallas con datos reales o marcadas explícitamente como ejemplo | ver [Correr el frontend](#correr-el-frontend) |

Dos decisiones de dominio que valen la pena explicar:

- **La categoría sugerida de un comercio es por usuario, no global.** Aunque el catálogo de
  comercios (`Comercio`) se comparte entre todos, lo que cada quien clasifica como "Alimentación"
  o "Transporte" es suyo -dos personas pueden categorizar el mismo supermercado distinto. Por eso
  existe `ComercioCategoriaSugerida` como tabla intermedia por `(usuario, comercio)`, en vez de un
  campo `categoria_sugerida` directo en `Comercio`.
- **Un presupuesto solo guarda su límite.** `monto_consumido` y su estado se calculan en cada
  petición combinando el límite con los comprobantes reales del período -no existe todavía un
  proceso transaccional que vaya actualizando un consumo guardado, así que no había honestidad en
  fingir que ese número persiste.

### Caché de comprobantes y sincronización incremental

Hasta hace poco, cada una de estas pantallas releía y reparseaba la bandeja completa del proveedor
en cada petición: con ~110 mensajes, eso son ~110 peticiones HTTP a Microsoft por cada carga de
pantalla, siempre -tuviera o no correo nuevo. Ahora el resultado de parsear cada mensaje se guarda
una sola vez en `Comprobante` ([`comprobante.py`](src/app/data/models/comprobante.py)), con
`mensaje_id` como clave de deduplicación: sincronizar una bandeja ya al día no vuelve a pedirle el
cuerpo a ningún mensaje, solo lista metadatos para ver si hay algo nuevo. `resumen_financiero`
-de donde salen comercios, presupuestos y los tres reportes- sincroniza sola antes de leer, así
que ninguna pantalla necesitó cambiar para beneficiarse. El endpoint
`POST /cuentas-correo/{id}/sincronizar` existe aparte para forzar el pull y confirmar cuánto trajo
de nuevo.

En números, contra un buzón real de ~113 comprobantes: primera carga (bandeja vacía) ~24s, carga
siguiente (bandeja al día) menos de 1s.

---

## Cómo correr la aplicación

Necesitás **Python 3.12 o superior** (nosotros usamos 3.14). **No hace falta Docker para esta
parte**: por defecto la aplicación usa SQLite local y crea el archivo sola al arrancar -así arranca
también en integración continua, que no levanta Docker.

### Conectarla a PostgreSQL en vez de SQLite

Con `docker compose up -d` corriendo (ver [Cómo levantar las bases de
datos](#cómo-levantar-las-bases-de-datos)), esta misma aplicación puede usar esa base en lugar del
archivo local. Es la propia `Base.metadata.create_all()` la que crea las tablas -el esquema que
migra Flyway (`db/postgres/migrations/`) es el modelo original de la propuesta de dominio, un
ejercicio aparte del Laboratorio 2 que no comparte base con la app en ejecución. Por eso Flyway no
corre con el `docker compose up -d` normal (ver el comentario al inicio de `docker-compose.yml`):
si alguna vez levantaste el perfil `flyway` contra esta misma base, hay que vaciar el esquema
primero (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) porque los nombres de tabla chocan.

En el `.env` (copiado de `.env.ejemplo`):

```bash
GASTONOMO_URL_BASE_DATOS=postgresql+psycopg://gastonomo:gastonomo_local@localhost:5432/gastonomo
```

Sin esa variable, sigue usando SQLite exactamente como antes.

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
| `GET` | `/api/cuentas-correo/{id}/comprobante?usuario_id=1&mensaje_id=…` | Lee y parsea el comprobante de un mensaje puntual |
| `GET` | `/api/cuentas-correo/{id}/resumen-financiero?usuario_id=1` | Sincroniza lo nuevo y suma por mes los comprobantes ya cacheados |
| `POST` | `/api/cuentas-correo/{id}/sincronizar?usuario_id=1` | Fuerza el pull de correo nuevo, sin pedir además todo el resumen |
| `GET` | `/api/cuentas-correo/{id}/comercios?usuario_id=1` | Resuelve y clasifica los comercios de esos comprobantes |
| `GET` | `/api/cuentas-correo/{id}/presupuestos?usuario_id=1&anio=2026&mes=9` | Estado de los presupuestos del período, contra el gasto real de ese mismo período |
| `GET` | `/api/cuentas-correo/{id}/reportes/movimientos.csv?usuario_id=1` | Exporta los movimientos reconocidos a CSV |
| `GET` | `/api/cuentas-correo/{id}/reportes/movimientos.xlsx?usuario_id=1` | Exporta los movimientos reconocidos a Excel |
| `GET` | `/api/cuentas-correo/{id}/reportes/resumen.pdf?usuario_id=1` | Exporta un reporte del mes más reciente en PDF |
| `DELETE` | `/api/cuentas-correo/{id}?usuario_id=1` | Desvincula un buzón |
| `POST` | `/api/comercios/{id}/categoria` | Asigna o corrige la categoría sugerida de un comercio, para ese usuario |
| `POST` | `/api/presupuestos` | Crea o corrige el presupuesto de una categoría y período |
| `GET` | `/api/presupuestos?usuario_id=1&anio=2026&mes=9` | Lista los presupuestos guardados de un período |
| `DELETE` | `/api/presupuestos/{id}?usuario_id=1` | Elimina un presupuesto |

Los tres primeros no necesitan nada extra. Todo lo que empieza con `/api/cuentas-correo/{id}/…`
necesita un buzón ya vinculado con credenciales reales de Microsoft/Google — ver la sección
**Vinculación de correo** más abajo.

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
│   ├── routers/        salud.py · categorias.py · cuentas_correo.py · comercios.py ·
│   │                   presupuestos.py · reportes.py
│   ├── schemas.py      DTOs de entrada y salida
│   └── dependencies.py arma los servicios con sus repositorios
│
├── business/       → Reglas del negocio. No sabe que existe HTTP.
│   ├── services/        categoria_service.py · cuenta_correo_service.py ·
│   │                    comercio_service.py · presupuesto_service.py · resumen_service.py
│   │   └── correo/      proveedor.py · outlook.py · gmail.py (hablan con Microsoft/Google)
│   ├── parsers/          comprobante_bac.py (lee notificaciones de BAC con regex)
│   ├── seguridad/        cifrado.py (cifra los tokens antes de guardarlos)
│   └── errors.py        violaciones de reglas del dominio
│
├── data/           → Entidades y consultas. No contiene reglas de negocio.
│   ├── models/          usuario.py · categoria.py · cuenta_correo.py · comercio.py ·
│   │                    comercio_categoria_sugerida.py · presupuesto.py · comprobante.py ·
│   │                    base.py · enums.py · tipos.py
│   └── repositories/    el único lugar del sistema que consulta datos
│
├── config/         → Lo que cambia entre máquinas.
│   ├── settings.py      nombre, versión, URL de la base, credenciales OAuth
│   ├── database.py      motor, sesión y creación de tablas
│   └── cliente_http.py  cliente HTTP compartido hacia Microsoft/Google
│
└── main.py         → Arma la app, CORS, y traduce errores de negocio a códigos HTTP.
```

El frontend vive aparte, en [`frontend/`](frontend/) — ver [Correr el frontend](#correr-el-frontend).

Tres decisiones sostienen la separación, ya que Python no la impone por sí solo:

1. El servicio recibe una **dataclass propia** (`CrearCategoriaComando`), no un modelo de FastAPI.
2. El repositorio **nunca confirma la transacción**: el `commit` lo hace el servicio, que es el
   único que sabe si la operación de negocio completa terminó bien.
3. Los errores de negocio son **excepciones propias** sin ninguna referencia a HTTP; `main.py` es
   el único archivo que las traduce a códigos de respuesta.

---

## Vinculación de correo (Outlook y Gmail)

El sistema vincula un buzón de Outlook o de Gmail vía OAuth2 y, una vez vinculado, lee sus
mensajes de BAC Credomatic, los parsea con
[`business/parsers/comprobante_bac.py`](src/app/business/parsers/comprobante_bac.py) y arma con
eso el resumen financiero, la clasificación por comercio, el estado de los presupuestos y los
reportes exportables -ver [Funcionalidades adelantadas](#funcionalidades-adelantadas-clasificación-presupuestos-y-reportes)
más arriba. Es la base del Proceso 2 de ingesta de comprobantes descrito en la
[Propuesta de Dominio](docs/propuesta-dominio.md); lo que falta de ese proceso es la parte
transaccional -conciliar contra un presupuesto guardado en vez de calcularlo al vuelo, y sumar
otros bancos además de BAC.

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

Abre en `http://localhost:5173`. Por ahora no hay login: se elige un `usuario_id` desde el
encabezado (el Laboratorio 1 siembra el usuario de demostración con id `1`).

Sin credenciales de Microsoft/Google configuradas, el botón de conectar igual redirige al proveedor
real, que rechaza la solicitud con un error legible (`unauthorized_client`) — es la forma de
confirmar que el flujo está bien armado antes de tener las credenciales a mano. Con un buzón real
vinculado, estas pantallas quedan disponibles:

| Pantalla | Con qué datos trabaja |
|---|---|
| **Resumen** | Gasto real del mes, tendencia, top comercios y calendario, extraídos en vivo del buzón vinculado |
| **Categorías** | Categorías reales del usuario; comercios ya clasificados agrupados por categoría, y los pendientes de clasificar |
| **Presupuestos** | Alta y baja de presupuestos reales por categoría y período, con su estado calculado contra el gasto real |
| **Reportes** | Descarga de CSV, Excel y PDF de los movimientos reales |
| **Conectar correo** | Vincular o desvincular Outlook y Gmail |
| **Bancos** *(datos de ejemplo)* | Prototipo de la pantalla, marcado explícitamente como no conectado todavía |
| **Ajustes** *(datos de ejemplo)* | Prototipo de la pantalla, marcado explícitamente como no conectado todavía |

Cada comprobante de BAC se lee y se guarda una sola vez -ver
[Caché de comprobantes](#caché-de-comprobantes-y-sincronización-incremental) más abajo. La primera
carga de un buzón nuevo puede tardar varios segundos; las siguientes, con la bandeja ya al día,
son casi instantáneas.

---

## Documentación

| Documento | Qué contiene |
|---|---|
| [Modelo de datos](docs/modelo-de-datos.md) | **Laboratorio 2.** El esquema relacional, su normalización, sus restricciones e índices justificados, y el subdominio de MongoDB con su justificación completa. |
| [Propuesta de Dominio](docs/propuesta-dominio.md) | El negocio, los actores, las entidades y los 2 procesos con sus reglas, cálculos y validaciones. |
| [Arquitectura](docs/arquitectura.md) | Diagramas de capas, recorrido de una petición, modelo entidad-relación y despliegue previsto. |
| [ADR-001 · Elección del stack](docs/adr/ADR-001-eleccion-del-stack.md) | Por qué Python + FastAPI + PostgreSQL + React, qué descartamos y qué nos cuesta. |
| [ADR-002 · Subdominio documental](docs/adr/ADR-002-subdominio-documental-en-mongodb.md) | Por qué la trazabilidad de la compra va en MongoDB incrustada, qué candidatos descartamos y qué invalidaría la decisión. |
| [ADR-003 · Flyway para las migraciones](docs/adr/ADR-003-flyway-para-las-migraciones.md) | Por qué Flyway en un contenedor en lugar de Alembic, y qué nos cuesta. |

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
- [x] **Laboratorio 2** *(entregado)* — Capa de datos completa: PostgreSQL con Flyway, subdominio
      documental en MongoDB, restricciones e índices probados. Ver
      [Qué incluye este laboratorio](#qué-incluye-este-laboratorio).
- [x] **Vinculación OAuth2 de buzones** *(adelantado, fuera de orden)* — Outlook y Gmail.
      Ver [Vinculación de correo](#vinculación-de-correo-outlook-y-gmail).
- [x] **Parser de comprobantes de BAC** *(adelantado)* — probado contra notificaciones reales,
      confianza 1.0 en los ocho campos. [`comprobante_bac.py`](src/app/business/parsers/comprobante_bac.py)
- [x] **Clasificación por comercio, presupuestos y reportes** *(adelantado)* — contra correo real,
      con estado de presupuesto calculado en vivo y exportación a CSV/Excel/PDF.
      Ver [Funcionalidades adelantadas](#funcionalidades-adelantadas-clasificación-presupuestos-y-reportes).
- [x] **Frontend completo** *(adelantado)* — siete pantallas; cinco con datos reales, dos marcadas
      explícitamente como prototipo. Ver [Correr el frontend](#correr-el-frontend).
- [x] **Caché local y sincronización incremental** *(adelantado)* — los comprobantes ya no se
      releen del proveedor en cada petición. Ver
      [Caché de comprobantes](#caché-de-comprobantes-y-sincronización-incremental).
- [x] **La aplicación puede correr sobre PostgreSQL** *(adelantado)* — `GASTONOMO_URL_BASE_DATOS`
      la conecta al Postgres de `docker compose up -d` en vez de SQLite, con su propio esquema
      (Flyway, el del Laboratorio 2, queda detrás de un perfil aparte a propósito -no compiten por
      la misma base). Ver [Conectarla a PostgreSQL](#conectarla-a-postgresql-en-vez-de-sqlite).

Pendiente:

- [ ] Conectar la aplicación a MongoDB para lo que corresponda al subdominio documental
- [ ] Vinculación de Gmail en el frontend (el backend ya soporta el proveedor)
- [ ] Sumar otros bancos además de BAC, contra una notificación real de cada uno
- [ ] Proceso transaccional de conciliación: acumular el consumo de un presupuesto como una
      `Compra` de negocio de verdad, en vez de recalcularlo en cada consulta a partir de
      `Comprobante` -la caché resuelve la lentitud, no la falta de esa tubería
- [ ] Autenticación y roles (titular, administrador) — hoy el `usuario_id` se elige a mano
- [ ] Pruebas automatizadas de frontend (el backend tiene 136 pruebas; el frontend, ninguna todavía)
