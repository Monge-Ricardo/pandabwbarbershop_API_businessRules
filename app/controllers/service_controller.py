from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.clients.crud_client import crud_client
from app.models.schemas.service_schema import ServiceCreate, ServiceUpdate, ServiceResponse
from app.middleware.auth import get_current_user

router = APIRouter(tags=["Services"])

async def check_is_barbershop_member(user_id: str, barbershop_id: str):
    """
    Verifica si el usuario es miembro activo de la barbería (Barbero o Dueño).
    Mapea con la restricción HU27 (cada barbero o miembro autorizado gestiona servicios).
    """
    memberships = await crud_client.list_members(barbershop_id=barbershop_id, user_id=user_id)
    if not memberships or memberships[0]["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restricción: Debe ser un miembro activo (Barbero/Dueño) de la barbería para realizar esta acción."
        )

@router.get("/services", response_model=List[ServiceResponse])
async def list_global_services():
    """
    Obtiene la lista de todos los servicios registrados en todo el sistema.
    """
    services = await crud_client.list_services()
    return [
        {
            "service_id": s["id"],
            "name": s["name"],
            "price": float(s["price"]),
            "is_active": s["is_active"],
            "description": s["description"],
            "duration_minutes": s["duration_minutes"],
            "barbershop_id": s["barbershop_id"]
        }
        for s in services
    ]

@router.get("/barbershops/{shop_id}/services", response_model=List[ServiceResponse])
async def list_shop_services(shop_id: str):
    """
    Obtiene todos los servicios ofrecidos por una barbería específica.
    """
    # Verify if shop exists
    shop = await crud_client.get_barbershop(shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbería no encontrada."
        )

    services = await crud_client.list_services(barbershop_id=shop_id)
    return [
        {
            "service_id": s["id"],
            "name": s["name"],
            "price": float(s["price"]),
            "is_active": s["is_active"],
            "description": s["description"],
            "duration_minutes": s["duration_minutes"],
            "barbershop_id": s["barbershop_id"]
        }
        for s in services
    ]

@router.post("/barbershops/{shop_id}/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(shop_id: str, body: ServiceCreate, current_user: dict = Depends(get_current_user)):
    """
    Crea un nuevo servicio dentro de una barbería.
    Solo miembros (Barberos o Dueños) autorizados de la barbería pueden crearlo (HU12).
    """
    if body.barbershop_id != shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID de la barbería en la ruta no coincide con el del cuerpo."
        )

    # Verify if shop exists
    shop = await crud_client.get_barbershop(shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbería no encontrada."
        )

    # Enforce HU27 / HU12
    await check_is_barbershop_member(current_user["id"], shop_id)

    new_service = await crud_client.create_service(
        barbershop_id=shop_id,
        name=body.name,
        description=body.description,
        price=body.price,
        duration_minutes=body.duration_minutes
    )
    
    return {
        "service_id": new_service["id"],
        "name": new_service["name"],
        "price": float(new_service["price"]),
        "is_active": new_service["is_active"],
        "description": new_service["description"],
        "duration_minutes": new_service["duration_minutes"],
        "barbershop_id": new_service["barbershop_id"]
    }

@router.get("/barbershops/{shop_id}/services/{service_id}", response_model=ServiceResponse)
async def get_service_details(shop_id: str, service_id: str):
    """
    Obtiene los detalles de un servicio específico.
    """
    service = await crud_client.get_service(service_id)
    if not service or service["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado en esta barbería."
        )
    return {
        "service_id": service["id"],
        "name": service["name"],
        "price": float(service["price"]),
        "is_active": service["is_active"],
        "description": service["description"],
        "duration_minutes": service["duration_minutes"],
        "barbershop_id": service["barbershop_id"]
    }

@router.put("/barbershops/{shop_id}/services/{service_id}", response_model=ServiceResponse)
async def update_service_details(shop_id: str, service_id: str, body: ServiceUpdate, current_user: dict = Depends(get_current_user)):
    """
    Actualiza la información de un servicio.
    Solo miembros (Barberos o Dueños) autorizados pueden editarlo (HU13).
    """
    # Enforce membership check
    await check_is_barbershop_member(current_user["id"], shop_id)

    service = await crud_client.get_service(service_id)
    if not service or service["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado en esta barbería."
        )

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return {
            "service_id": service["id"],
            "name": service["name"],
            "price": float(service["price"]),
            "is_active": service["is_active"],
            "description": service["description"],
            "duration_minutes": service["duration_minutes"],
            "barbershop_id": service["barbershop_id"]
        }

    updated = await crud_client.update_service(service_id, update_data)
    return {
        "service_id": updated["id"],
        "name": updated["name"],
        "price": float(updated["price"]),
        "is_active": updated["is_active"],
        "description": updated["description"],
        "duration_minutes": updated["duration_minutes"],
        "barbershop_id": updated["barbershop_id"]
    }

@router.delete("/barbershops/{shop_id}/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_details(shop_id: str, service_id: str, current_user: dict = Depends(get_current_user)):
    """
    Elimina un servicio de la barbería.
    Solo miembros (Barberos o Dueños) autorizados pueden eliminarlo (HU14).
    """
    # Enforce membership check
    await check_is_barbershop_member(current_user["id"], shop_id)

    service = await crud_client.get_service(service_id)
    if not service or service["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado en esta barbería."
        )

    await crud_client.delete_service(service_id)
    return None
