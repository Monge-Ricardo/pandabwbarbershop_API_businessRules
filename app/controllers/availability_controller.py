from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from app.clients.crud_client import crud_client
from app.models.schemas.availability_schema import AvailabilityCreate, AvailabilityUpdate, AvailabilityResponse
from app.middleware.auth import get_current_user
from app.controllers.appointment_controller import parse_time_str

router = APIRouter(prefix="/barbers", tags=["Barber Availabilities"])

async def check_can_manage_availability(current_user: dict, barber_id: str):
    """Enforces that only the barber themselves or an owner can manage availability."""
    if current_user["id"] != barber_id and current_user.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permiso denegado: Solo el barbero dueño de esta disponibilidad o el propietario de la barbería pueden realizar cambios."
        )

@router.get("/{barber_id}/availabilities", response_model=List[AvailabilityResponse])
async def list_barber_availabilities(barber_id: str):
    """
    Lista la disponibilidad registrada para un barbero específico (HU21).
    """
    raw_av = await crud_client.list_availabilities(barber_id=barber_id)
    return [
        {
            "availability_id": a["id"],
            "day_of_week": a["day_of_week"],
            "start_time": parse_time_str(a["start_time"]),
            "end_time": parse_time_str(a["end_time"]),
            "is_available": a["is_available"]
        }
        for a in raw_av
    ]

@router.post("/{barber_id}/availabilities", response_model=AvailabilityResponse, status_code=status.HTTP_201_CREATED)
async def create_barber_availability(barber_id: str, body: AvailabilityCreate, current_user: dict = Depends(get_current_user)):
    """
    Registra un bloque de disponibilidad para un barbero.
    """
    await check_can_manage_availability(current_user, barber_id)

    new_av = await crud_client.create_availability(
        barbershop_id=body.barbershop_id,
        barber_id=barber_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time.strftime("%H:%M:%S"),
        end_time=body.end_time.strftime("%H:%M:%S"),
        is_available=body.is_available
    )

    return {
        "availability_id": new_av["id"],
        "day_of_week": new_av["day_of_week"],
        "start_time": parse_time_str(new_av["start_time"]),
        "end_time": parse_time_str(new_av["end_time"]),
        "is_available": new_av["is_available"]
    }

@router.put("/{barber_id}/availabilities/{availability_id}", response_model=AvailabilityResponse)
async def update_barber_availability(barber_id: str, availability_id: str, body: AvailabilityUpdate, current_user: dict = Depends(get_current_user)):
    """
    Actualiza la disponibilidad de un barbero.
    """
    await check_can_manage_availability(current_user, barber_id)

    av = await crud_client.get_availability(availability_id)
    if not av or av["barber_id"] != barber_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloque de disponibilidad no encontrado para este barbero."
        )

    update_data = {}
    if body.day_of_week is not None:
        update_data["day_of_week"] = body.day_of_week
    if body.start_time is not None:
        update_data["start_time"] = body.start_time.strftime("%H:%M:%S")
    if body.end_time is not None:
        update_data["end_time"] = body.end_time.strftime("%H:%M:%S")
    if body.is_available is not None:
        update_data["is_available"] = body.is_available

    if not update_data:
        return {
            "availability_id": av["id"],
            "day_of_week": av["day_of_week"],
            "start_time": parse_time_str(av["start_time"]),
            "end_time": parse_time_str(av["end_time"]),
            "is_available": av["is_available"]
        }

    updated = await crud_client.update_availability(availability_id, update_data)
    return {
        "availability_id": updated["id"],
        "day_of_week": updated["day_of_week"],
        "start_time": parse_time_str(updated["start_time"]),
        "end_time": parse_time_str(updated["end_time"]),
        "is_available": updated["is_available"]
    }

@router.delete("/{barber_id}/availabilities/{availability_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_barber_availability(barber_id: str, availability_id: str, current_user: dict = Depends(get_current_user)):
    """
    Elimina un bloque de disponibilidad del barbero.
    """
    await check_can_manage_availability(current_user, barber_id)

    av = await crud_client.get_availability(availability_id)
    if not av or av["barber_id"] != barber_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bloque de disponibilidad no encontrado para este barbero."
        )

    await crud_client.delete_availability(availability_id)
    return None
