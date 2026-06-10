from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.controllers import (
    auth_controller,
    user_controller,
    barbershop_controller,
    service_controller,
    product_controller,
    appointment_controller,
    availability_controller,
    invitation_controller,
    dashboard_controller,
)

app = FastAPI(
    title="SharkHub Business Rules API",
    description="Servidor API REST que se encarga de las reglas de negocio, RBAC, y flujo de reservas de SharkHub.",
    version="1.0.0"
)

# Enable CORS for decentralized frontend consumption
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers (preserving the paths/prefixes as needed)
# All business endpoints are served directly on the root or configured prefixes
app.include_router(auth_controller.router)
app.include_router(user_controller.router)
app.include_router(barbershop_controller.router)
app.include_router(service_controller.router)
app.include_router(product_controller.router)
app.include_router(appointment_controller.router)
app.include_router(availability_controller.router)
app.include_router(invitation_controller.router)
app.include_router(dashboard_controller.router)

from fastapi import Response, status, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException

@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    err_str = str(exc)
    if "Error de red al conectar al API de datos" in err_str:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Servicio temporalmente no disponible: La API CRUD de Base de Datos está apagada o fuera de línea. Por favor, asegúrate de levantar el servidor CRUD en el puerto 3000."
            }
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": err_str}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, str) and "Error de red al conectar al API de datos" in exc.detail:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Servicio temporalmente no disponible: La API CRUD de Base de Datos está apagada o fuera de línea. Por favor, asegúrate de levantar el servidor CRUD en el puerto 3000."
            }
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )

@app.get("/health", tags=["System"])
async def health_check(response: Response):
    """
    Verifica el estado del servidor de reglas de negocio y de la base de datos (CRUD API).
    """
    from app.clients.crud_client import crud_client
    import httpx
    
    crud_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{crud_client.base_url}/health", timeout=2.0)
            if res.status_code == 200:
                crud_status = "connected"
            else:
                crud_status = f"unhealthy (status {res.status_code})"
    except Exception as e:
        crud_status = f"offline ({str(e)})"

    if crud_status != "connected":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "Business Rules API",
            "database_crud_api": {
                "status": "offline",
                "message": "La API CRUD (base de datos) no responde. El servicio principal de datos está caído.",
                "error": crud_status
            }
        }

    return {
        "status": "healthy",
        "service": "Business Rules API",
        "database_crud_api": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
