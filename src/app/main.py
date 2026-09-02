"""Punto de entrada: arma la aplicacion y traduce errores de negocio a HTTP.

Este es el unico archivo del sistema autorizado a conocer las dos cosas a la vez:
las excepciones del dominio y los codigos de respuesta HTTP.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError

from app.business.errors import (
    DatosInvalidos,
    ErrorDeProveedorExterno,
    RecursoNoEncontrado,
    ReglaDeNegocioViolada,
)
from app.config.cliente_http import cerrar_cliente_http
from app.config.database import crear_tablas, sembrar_usuario_de_demostracion
from app.config.settings import obtener_configuracion
from app.presentation.routers import (
    categorias,
    comercios,
    cuentas_correo,
    presupuestos,
    reportes,
    salud,
)

configuracion = obtener_configuracion()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    """Prepara el esquema antes de atender la primera peticion y cierra recursos al apagar."""
    crear_tablas()
    sembrar_usuario_de_demostracion()
    yield
    cerrar_cliente_http()


app = FastAPI(
    title=configuracion.nombre_aplicacion,
    version=configuracion.version,
    summary="Control de gastos personales por categorias",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configuracion.origenes_permitidos,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(salud.router)
app.include_router(categorias.router)
app.include_router(cuentas_correo.router)
app.include_router(comercios.router)
app.include_router(presupuestos.router)
app.include_router(reportes.router)


@app.exception_handler(DatosInvalidos)
async def manejar_datos_invalidos(_: Request, error: DatosInvalidos) -> JSONResponse:
    """422: el dato llego bien formado pero no cumple una regla del dominio."""
    # El 422 va como numero y no como constante de Starlette: la constante cambio
    # de nombre entre versiones y el codigo no.
    return JSONResponse(status_code=422, content={"detalle": str(error)})


@app.exception_handler(RecursoNoEncontrado)
async def manejar_recurso_no_encontrado(_: Request, error: RecursoNoEncontrado) -> JSONResponse:
    """404: se referencio algo que no existe o que no es del titular."""
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detalle": str(error)})


@app.exception_handler(ReglaDeNegocioViolada)
async def manejar_regla_violada(_: Request, error: ReglaDeNegocioViolada) -> JSONResponse:
    """409: la operacion choca con el estado actual del sistema."""
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detalle": str(error)})


@app.exception_handler(ErrorDeProveedorExterno)
async def manejar_error_de_proveedor_externo(
    _: Request, error: ErrorDeProveedorExterno
) -> JSONResponse:
    """502: Microsoft o Google rechazaron la solicitud o no respondieron."""
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detalle": str(error)})


@app.exception_handler(DataError)
async def manejar_error_de_datos(_: Request, error: DataError) -> JSONResponse:
    """422: un valor con la forma correcta no le calza al tipo real de la columna.

    Pydantic valida la forma (tipos, largos declarados), no los límites
    exactos de cada columna -un id absurdamente grande, por ejemplo, pasa la
    validación de FastAPI sin problema y solo revienta cuando Postgres
    intenta convertirlo a INTEGER. Sin este manejador, cualquier `DataError`
    de SQLAlchemy se colaba como un 500 crudo; acá se le da la forma del
    resto de los errores de negocio, sin repetir el mensaje exacto de
    Postgres -viene en inglés y con detalles internos que no le sirven a
    quien llama la API.
    """
    return JSONResponse(
        status_code=422, content={"detalle": "Uno de los valores enviados no es válido."}
    )
