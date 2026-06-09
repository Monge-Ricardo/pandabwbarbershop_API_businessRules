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

@app.get("/health", tags=["System"])
async def health_check():
    """
    Verifica el estado del servidor de reglas de negocio.
    """
    return {
        "status": "healthy",
        "service": "Business Rules API"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
