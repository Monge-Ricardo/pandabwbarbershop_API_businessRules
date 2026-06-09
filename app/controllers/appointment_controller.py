from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime, date, time
from app.clients.crud_client import crud_client
from app.models.schemas.appointment_schema import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse, AppointmentServiceBind
)
from app.models.schemas.service_schema import ServiceResponse
from app.middleware.auth import get_current_user

router = APIRouter(tags=["Appointments"])

def parse_time_str(t_val) -> time:
    """Helper to convert database or schema time string to datetime.time."""
    if isinstance(t_val, time):
        return t_val
    if isinstance(t_val, str):
        # Handle formats like "10:00:00", "10:00:00.000Z", "10:00"
        t_clean = t_val.split("T")[-1].split("Z")[0].split(".")[0]
        # t_clean is now "HH:MM:SS" or "HH:MM"
        parts = t_clean.split(":")
        return time(int(parts[0]), int(parts[1]))
    if isinstance(t_val, datetime):
        return t_val.time()
    raise ValueError(f"No se pudo parsear el valor de tiempo: {t_val}")

def parse_date_str(d_val) -> date:
    """Helper to convert date value to datetime.date."""
    if isinstance(d_val, date):
        return d_val
    if isinstance(d_val, str):
        return datetime.strptime(d_val.split("T")[0], "%Y-%m-%d").date()
    if isinstance(d_val, datetime):
        return d_val.date()
    raise ValueError(f"No se pudo parsear el valor de fecha: {d_val}")

# --- BUSINESS LOGIC VALDATIONS ---

async def validate_appointment_rules(
    barbershop_id: str,
    barber_id: str,
    app_date: date,
    start_time: time,
    end_time: time
):
    """
    Verifica las reglas de negocio críticas para agendar una cita:
    1. Que el barbero sea un miembro activo de la barbería.
    2. Que el horario esté dentro de la disponibilidad del barbero (HU21).
    3. Que no haya colisiones de horario / doble agenda para el barbero (HU28).
    """
    # 1. Active member check
    members = await crud_client.list_members(barbershop_id=barbershop_id, user_id=barber_id)
    if not members or members[0]["role"].upper() != "BARBER" or members[0]["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El barbero especificado no es un miembro activo de esta barbería."
        )

    # 2. Availability check (HU21)
    day_of_week = app_date.isoweekday() # Monday=1, ..., Sunday=7
    availabilities = await crud_client.list_availabilities(barber_id=barber_id, barbershop_id=barbershop_id)
    
    matching_av = None
    for av in availabilities:
        if av["day_of_week"] == day_of_week and av["is_available"]:
            av_start = parse_time_str(av["start_time"])
            av_end = parse_time_str(av["end_time"])
            if av_start <= start_time and end_time <= av_end:
                matching_av = av
                break

    if not matching_av:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El barbero no está disponible en este horario. Día de la semana: {day_of_week}."
        )

    # 3. Overlap check / Double-booking prevention (HU28)
    existing_appointments = await crud_client.list_appointments(
        barber_id=barber_id,
        appointment_date=str(app_date)
    )

    for app in existing_appointments:
        if app["status"] == "cancelled":
            continue
            
        existing_start = parse_time_str(app["start_time"])
        existing_end = parse_time_str(app["end_time"])

        # Overlap condition: start1 < end2 AND start2 < end1
        if start_time < existing_end and existing_start < end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Conflicto de horario: El barbero ya tiene una cita agendada que coincide con este rango."
            )

# --- APPOINTMENTS ENDPOINTS ---

@router.get("/appointments", response_model=List[AppointmentResponse])
async def list_appointments(
    barbershop_id: Optional[str] = None,
    client_id: Optional[str] = None,
    barber_id: Optional[str] = None,
    appointment_date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Lista las citas registradas en el sistema. Filtra según rol y parámetros provistos (HU23 / HU24).
    """
    # Owners can list all. Clients and barbers can only list their own unless filtered.
    role = current_user.get("role", "client").lower()
    
    if role == "client":
        client_id = current_user["id"]
    elif role == "barber":
        barber_id = current_user["id"]

    raw_apps = await crud_client.list_appointments(
        barbershop_id=barbershop_id,
        client_id=client_id,
        barber_id=barber_id,
        appointment_date=appointment_date
    )
    
    return [
        {
            "appointment_id": a["id"],
            "barber_id": a["barber_id"],
            "client_id": a["client_id"],
            "appointment_date": parse_date_str(a["appointment_date"]),
            "status": a["status"] or "pending",
            "notes": a["notes"],
            "start_time": parse_time_str(a["start_time"]),
            "end_time": parse_time_str(a["end_time"]),
            "barbershop_id": a["barbershop_id"]
        }
        for a in raw_apps
    ]

@router.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(body: AppointmentCreate, current_user: dict = Depends(get_current_user)):
    """
    Crea una nueva cita (reserva). Valida disponibilidad y colisiones de horarios (HU20 / HU28).
    """
    # Enforce that client_id matches the logged-in user unless the caller is an owner/barber
    role = current_user.get("role", "client").lower()
    if role == "client" and body.client_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para agendar citas para otro cliente."
        )

    # Validate business rules
    await validate_appointment_rules(
        barbershop_id=body.barbershop_id,
        barber_id=body.barber_id,
        app_date=body.appointment_date,
        start_time=body.start_time,
        end_time=body.end_time
    )

    # Create the appointment
    new_app = await crud_client.create_appointment(
        barbershop_id=body.barbershop_id,
        client_id=body.client_id,
        barber_id=body.barber_id,
        appointment_date=str(body.appointment_date),
        start_time=body.start_time.strftime("%H:%M:%S"),
        end_time=body.end_time.strftime("%H:%M:%S"),
        notes=body.notes
    )

    # Bind service if provided
    if body.service_id:
        try:
            await crud_client.create_appointment_service(
                appointment_id=new_app["id"],
                service_id=body.service_id
            )
        except Exception as e:
            # Cleanup appointment on failure to link service
            await crud_client.delete_appointment(new_app["id"])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al vincular el servicio de la cita: {str(e)}"
            )

    return {
        "appointment_id": new_app["id"],
        "barber_id": new_app["barber_id"],
        "client_id": new_app["client_id"],
        "appointment_date": parse_date_str(new_app["appointment_date"]),
        "status": new_app["status"] or "pending",
        "notes": new_app["notes"],
        "start_time": parse_time_str(new_app["start_time"]),
        "end_time": parse_time_str(new_app["end_time"]),
        "barbershop_id": new_app["barbershop_id"]
    }

@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment_details(appointment_id: str, current_user: dict = Depends(get_current_user)):
    """
    Obtiene los detalles de una cita.
    """
    app = await crud_client.get_appointment(appointment_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cita no encontrada."
        )

    # Enforce reading permissions
    role = current_user.get("role", "client").lower()
    if role == "client" and app["client_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver esta cita."
        )
    if role == "barber" and app["barber_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para ver esta cita."
        )

    return {
        "appointment_id": app["id"],
        "barber_id": app["barber_id"],
        "client_id": app["client_id"],
        "appointment_date": parse_date_str(app["appointment_date"]),
        "status": app["status"] or "pending",
        "notes": app["notes"],
        "start_time": parse_time_str(app["start_time"]),
        "end_time": parse_time_str(app["end_time"]),
        "barbershop_id": app["barbershop_id"]
    }

@router.put("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment_details(appointment_id: str, body: AppointmentUpdate, current_user: dict = Depends(get_current_user)):
    """
    Modifica una cita existente. Si se modifica la fecha/hora, valida las reglas de disponibilidad y colisiones (HU25).
    """
    app = await crud_client.get_appointment(appointment_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cita no encontrada."
        )

    role = current_user.get("role", "client").lower()
    if role == "client" and app["client_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para modificar esta cita."
        )

    # Check if rescheduling requires validating rules
    reschedule_needed = False
    new_date = parse_date_str(app["appointment_date"])
    new_start = parse_time_str(app["start_time"])
    new_end = parse_time_str(app["end_time"])

    if body.appointment_date is not None and body.appointment_date != new_date:
        new_date = body.appointment_date
        reschedule_needed = True
    if body.start_time is not None and body.start_time != new_start:
        new_start = body.start_time
        reschedule_needed = True
    if body.end_time is not None and body.end_time != new_end:
        new_end = body.end_time
        reschedule_needed = True

    if reschedule_needed:
        await validate_appointment_rules(
            barbershop_id=app["barbershop_id"],
            barber_id=app["barber_id"],
            app_date=new_date,
            start_time=new_start,
            end_time=new_end
        )

    update_data = {}
    if body.status is not None:
        # Barbero o Dueño pueden aceptar/cancelar/completar cita (HU25)
        update_data["status"] = body.status
    if body.notes is not None:
        update_data["notes"] = body.notes
    if reschedule_needed:
        update_data["appointment_date"] = str(new_date)
        update_data["start_time"] = new_start.strftime("%H:%M:%S")
        update_data["end_time"] = new_end.strftime("%H:%M:%S")

    if not update_data:
        return {
            "appointment_id": app["id"],
            "barber_id": app["barber_id"],
            "client_id": app["client_id"],
            "appointment_date": parse_date_str(app["appointment_date"]),
            "status": app["status"] or "pending",
            "notes": app["notes"],
            "start_time": parse_time_str(app["start_time"]),
            "end_time": parse_time_str(app["end_time"]),
            "barbershop_id": app["barbershop_id"]
        }

    updated = await crud_client.update_appointment(appointment_id, update_data)
    return {
        "appointment_id": updated["id"],
        "barber_id": updated["barber_id"],
        "client_id": updated["client_id"],
        "appointment_date": parse_date_str(updated["appointment_date"]),
        "status": updated["status"] or "pending",
        "notes": updated["notes"],
        "start_time": parse_time_str(updated["start_time"]),
        "end_time": parse_time_str(updated["end_time"]),
        "barbershop_id": updated["barbershop_id"]
    }

@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_appointment(appointment_id: str, current_user: dict = Depends(get_current_user)):
    """
    Cancela o elimina una cita.
    """
    app = await crud_client.get_appointment(appointment_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cita no encontrada."
        )

    role = current_user.get("role", "client").lower()
    if role == "client" and app["client_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para cancelar esta cita."
        )

    await crud_client.delete_appointment(appointment_id)
    return None

# --- APPOINTMENT SERVICES ENDPOINTS ---

@router.get("/appointments/{appointment_id}/services", response_model=List[ServiceResponse])
async def list_appointment_linked_services(appointment_id: str, current_user: dict = Depends(get_current_user)):
    """
    Lista todos los servicios asociados a una cita.
    """
    relations = await crud_client.list_appointment_services(appointment_id=appointment_id)
    
    services = []
    for r in relations:
        s = await crud_client.get_service(r["service_id"])
        if s:
            services.append({
                "service_id": s["id"],
                "name": s["name"],
                "price": float(s["price"]),
                "is_active": s["is_active"],
                "description": s["description"],
                "duration_minutes": s["duration_minutes"],
                "barbershop_id": s["barbershop_id"]
            })
    return services

@router.post("/appointments/{appointment_id}/services", status_code=status.HTTP_201_CREATED)
async def link_service_to_appointment(appointment_id: str, body: AppointmentServiceBind, current_user: dict = Depends(get_current_user)):
    """
    Vincula un servicio a una cita.
    """
    # Verify appointment exists
    app = await crud_client.get_appointment(appointment_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cita no encontrada."
        )

    # Verify service exists
    srv = await crud_client.get_service(body.service_id)
    if not srv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado."
        )

    await crud_client.create_appointment_service(appointment_id, body.service_id)
    return {"appointment_id": appointment_id, "service_id": body.service_id, "message": "Servicio agregado a la cita"}

@router.delete("/appointments/{appointment_id}/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_service_from_appointment(appointment_id: str, service_id: str, current_user: dict = Depends(get_current_user)):
    """
    Desvincula un servicio de una cita.
    """
    await crud_client.delete_appointment_service_by_ids(appointment_id, service_id)
    return None
