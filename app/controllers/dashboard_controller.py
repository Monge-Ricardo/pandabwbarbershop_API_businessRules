import httpx
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Depends,
    Query,
    Header,
)
from typing import List, Optional, Tuple
from datetime import datetime, date, time, timedelta
from app.clients.crud_client import crud_client
from app.middleware.auth import get_current_user, require_role
from app.controllers.appointment_controller import parse_time_str, parse_date_str


APPOINTMENT_SLOT_INTERVAL_MINUTES = 30

router = APIRouter(prefix="/api", tags=["Role Dashboards (Owner, Barber, Customer)"])

# Helper to verify ownership of a shop
async def get_owner_barbershop_id(owner_id: str, request_barbershop_id: Optional[str] = None) -> str:
    memberships = await crud_client.list_members(user_id=owner_id)
    owned_ids = [m["barbershop_id"] for m in memberships if m["role"].upper() == "OWNER" and m["status"] == "active"]
    if not owned_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario actual no es propietario activo de ninguna barbería."
        )
    if request_barbershop_id and request_barbershop_id in owned_ids:
        return request_barbershop_id
    return owned_ids[0]

# Helper to verify barber belongs to a shop
async def get_barber_barbershop_id(barber_id: str) -> str:
    memberships = await crud_client.list_members(user_id=barber_id)
    for m in memberships:
        if m["role"].upper() == "BARBER" and m["status"] == "active":
            return m["barbershop_id"]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="El barbero actual no está activo en ninguna barbería."
    )

# ========================================================
# 👑 A. OWNER ENDPOINTS
# ========================================================

@router.get("/owner/barbershops", dependencies=[Depends(require_role(["owner"]))])
async def owner_list_barbershops(current_user: dict = Depends(get_current_user)):
    """
    Lista todas las sucursales (barberías) del dueño.
    """
    memberships = await crud_client.list_members(user_id=current_user["id"])
    owned_ids = [m["barbershop_id"] for m in memberships if m["role"].upper() == "OWNER" and m["status"] == "active"]
    shops = []
    for s_id in owned_ids:
        shop = await crud_client.get_barbershop(s_id)
        if shop:
            shops.append(shop)
    return shops

@router.put("/owner/barbershop", dependencies=[Depends(require_role(["owner"]))])
async def owner_update_barbershop(body: dict, current_user: dict = Depends(get_current_user), x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")):
    """
    Actualiza el perfil de la barbería del dueño autenticado.
    """
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    return await crud_client.update_barbershop(shop_id, body)

@router.get("/owner/barbershop", dependencies=[Depends(require_role(["owner"]))])
async def owner_get_barbershop(current_user: dict = Depends(get_current_user), x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")):
    """
    Obtiene la información de la barbería del dueño autenticado.
    """
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    return await crud_client.get_barbershop(shop_id)

@router.get("/owner/barbers", dependencies=[Depends(require_role(["owner"]))])
async def owner_list_barbers(current_user: dict = Depends(get_current_user), x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")):
    """
    Obtiene la lista de barberos asociados a la barbería del dueño autenticado.
    """
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    members = await crud_client.list_members(barbershop_id=shop_id)
    
    barber_members = [m for m in members if m["role"].lower() == "barber"]
    
    resolved = []
    for m in barber_members:
        user_profile = await crud_client.get_user(m["user_id"])
        resolved.append({
            "membership_id": m["id"],
            "member_id": m["id"],
            "id": m["user_id"],
            "user_id": m["user_id"],
            "full_name": user_profile["full_name"] if user_profile else "Barbero Desconocido",
            "name": user_profile["full_name"] if user_profile else "Barbero Desconocido",
            "email": user_profile["email"] if user_profile else "",
            "phone": user_profile["phone"] if user_profile else "",
            "status": m["status"]
        })
    return {"data": resolved}

@router.post("/owner/barbers", dependencies=[Depends(require_role(["owner"]))])
async def owner_add_barber(body: dict, current_user: dict = Depends(get_current_user), x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")):
    """
    Añade un barbero registrado a la barbería del dueño usando su correo electrónico.
    """
    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Se requiere el campo 'email'.")
        
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    
    # 1. Lookup user in public profiles
    profiles = await crud_client.list_users(email=email)
    if not profiles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró ningún usuario registrado con ese correo electrónico."
        )
    target_user = profiles[0]

    # 2. Add as barber member
    await crud_client.create_member(
        barbershop_id=shop_id,
        user_id=target_user["id"],
        role="barber",
        status="active"
    )

    return {"message": "Barbero asignado de manera exitosa"}

@router.patch("/owner/barbers/{member_id}/status", dependencies=[Depends(require_role(["owner"]))])
async def owner_patch_barber_status(member_id: str, body: dict, current_user: dict = Depends(get_current_user), x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")):
    """
    Cambia el estatus (active / inactive) de un miembro barbero.
    """
    new_status = body.get("status")
    if new_status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Estatus no válido. Use 'active' o 'inactive'.")
        
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    
    # Verify member exists and belongs to this shop
    member = await crud_client.get_member(member_id)
    if not member or member["barbershop_id"] != shop_id:
        raise HTTPException(status_code=404, detail="Miembro no encontrado en su barbería.")
        
    return await crud_client.update_member(member_id, {"status": new_status})

@router.get("/owner/appointments", dependencies=[Depends(require_role(["owner"]))])
async def owner_list_appointments(
    date: Optional[str] = None,
    barber_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")
):
    """
    Filtra citas de la barbería del dueño activo.
    """
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    return await crud_client.list_appointments(
        barbershop_id=shop_id,
        barber_id=barber_id,
        appointment_date=date
    )

@router.patch("/owner/appointments/{appointment_id}/status", dependencies=[Depends(require_role(["owner"]))])
async def owner_patch_appointment_status(appointment_id: str, body: dict, current_user: dict = Depends(get_current_user), x_barbershop_id: Optional[str] = Header(None, alias="X-Barbershop-Id")):
    """
    Modifica el estado de una cita (pending, confirmed, cancelled).
    """
    new_status = body.get("status")
    if new_status not in ["pending", "confirmed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Estado no válido.")
        
    shop_id = await get_owner_barbershop_id(current_user["id"], x_barbershop_id)
    
    # Verify appointment belongs to owner's shop
    appointment = await crud_client.get_appointment(appointment_id)
    if not appointment or appointment["barbershop_id"] != shop_id:
        raise HTTPException(status_code=404, detail="Cita no encontrada en su barbería.")
        
    return await crud_client.update_appointment(appointment_id, {"status": new_status})

# ========================================================
# 💈 B. BARBER ENDPOINTS
# ========================================================

@router.get("/barber/appointments", dependencies=[Depends(require_role(["barber"]))])
async def barber_list_appointments(date: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """
    Filtra la agenda de citas del barbero autenticado.
    """
    return await crud_client.list_appointments(
        barber_id=current_user["id"],
        appointment_date=date
    )

@router.post("/barber/services", dependencies=[Depends(require_role(["barber"]))])
async def barber_create_service(body: dict, current_user: dict = Depends(get_current_user)):
    """
    Registra un nuevo servicio en la barbería donde trabaja el barbero.
    """
    shop_id = await get_barber_barbershop_id(current_user["id"])
    return await crud_client.create_service(
        barbershop_id=shop_id,
        name=body["name"],
        description=body.get("description"),
        price=float(body["price"]),
        duration_minutes=int(body["duration_minutes"])
    )

@router.post("/barber/products", dependencies=[Depends(require_role(["barber"]))])
async def barber_create_product(body: dict, current_user: dict = Depends(get_current_user)):
    """
    Registra un nuevo producto en el inventario de la barbería donde trabaja.
    """
    shop_id = await get_barber_barbershop_id(current_user["id"])
    return await crud_client.create_product(
        barbershop_id=shop_id,
        name=body["name"],
        description=body.get("description"),
        price=float(body["price"]) if "price" in body else 0.0,
        stock=int(body["stock"]) if "stock" in body else 0,
        image_url=body.get("image_url")
    )

# ========================================================
# 👥 C. CUSTOMER ENDPOINTS
# ========================================================

@router.get("/customer/barbers")
async def customer_list_barbers():
    """
    Obtiene la lista de todos los barberos activos en el sistema,
    resolviendo sus nombres de usuario y las barberías a las que pertenecen.
    """
    members = await crud_client.list_members()
    barber_members = [m for m in members if m["role"].lower() == "barber" and m["status"] == "active"]
    
    resolved_barbers = []
    for m in barber_members:
        user_profile = await crud_client.get_user(m["user_id"])
        shop = await crud_client.get_barbershop(m["barbershop_id"])
        resolved_barbers.append({
            "id": m["user_id"],
            "full_name": user_profile["full_name"] if user_profile else "Barbero Desconocido",
            "barbershop_id": m["barbershop_id"],
            "barbershop_name": shop["name"] if shop else "Barbería"
        })
    return {"data": resolved_barbers}

@router.get("/customer/services")
async def customer_search_services(barbershop_id: Optional[str] = None):
    """
    Busca y filtra servicios activos.
    """
    services = await crud_client.list_services(barbershop_id=barbershop_id)
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
        for s in services if s["is_active"]
    ]

@router.get("/customer/available-times")
async def customer_get_available_times(
    barber_id: str = Query(...),
    service_id: str = Query(...),
    date: str = Query(...)  # YYYY-MM-DD
):
    """
    Calcula dinámicamente las horas de turnos libres para un barbero en una fecha y servicio específico.
    Filtra colisiones con citas existentes y respeta el horario de disponibilidad.
    """
    # 1. Verify service
    service = await crud_client.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    duration = timedelta(minutes=int(service["duration_minutes"]))
    shop_id = service["barbershop_id"]

    # 2. Get date day of week
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
    day_of_week = query_date.isoweekday()

    # 3. Find availability block
    availabilities = await crud_client.list_availabilities(barber_id=barber_id, barbershop_id=shop_id)
    matching_availability = None
    for availability in availabilities:
        if availability["day_of_week"] == day_of_week and availability["is_available"]:
            matching_availability = availability
            break
            
    if not matching_availability:
        return {"date": date, "available_slots": []}

    availability_start = parse_time_str(matching_availability["start_time"])
    availability_end = parse_time_str(matching_availability["end_time"])

    # 4. Fetch existing appointments
    appointments = await crud_client.list_appointments(barber_id=barber_id, appointment_date=date)
    active_appointments = [a for a in appointments if a["status"] != "cancelled"]

    # 5. Generate slots at APPOINTMENT_SLOT_INTERVAL_MINUTES intervals
    start_dt = datetime.combine(query_date, availability_start)
    end_dt = datetime.combine(query_date, availability_end)
    
    # Get current time in Ecuador (UTC-5)
    now_ecuador = datetime.utcnow() - timedelta(hours=5)
    
    slots = []
    current_dt = start_dt
    while current_dt + duration <= end_dt:
        slot_start = current_dt.time()
        slot_end = (current_dt + duration).time()
        
        # Check overlaps
        overlap = False
        for appointment in active_appointments:
            appointment_start = parse_time_str(appointment["start_time"])
            appointment_end = parse_time_str(appointment["end_time"])
            
            # overlap check
            if slot_start < appointment_end and appointment_start < slot_end:
                overlap = True
                break
                
        if not overlap:
            slot_datetime = datetime.combine(query_date, slot_start)
            if slot_datetime >= now_ecuador:
                slots.append(slot_start.strftime("%H:%M"))
            
        current_dt += timedelta(minutes=APPOINTMENT_SLOT_INTERVAL_MINUTES)

    return {
        "date": date,
        "available_slots": slots
    }

def _parse_booking_request_times(appointment_date_str: str, start_time_str: str, duration_min: int) -> Tuple[date, time, time]:
    """Parse date and start/end times from request inputs."""
    try:
        app_date = datetime.strptime(appointment_date_str, "%Y-%m-%d").date()
        parts = start_time_str.split(":")
        start_time = time(int(parts[0]), int(parts[1]))
        temp_dt = datetime.combine(app_date, start_time) + timedelta(minutes=duration_min)
        end_time = temp_dt.time()
        return app_date, start_time, end_time
    except (ValueError, IndexError, TypeError) as parse_error:
        raise HTTPException(
            status_code=400,
            detail=f"Error al parsear fecha u hora: {str(parse_error)}"
        )

async def _link_service_with_rollback(appointment_id: str, service_id: str) -> None:
    """Link service to appointment, rollback by deleting appointment on failure."""
    try:
        await crud_client.create_appointment_service(
            appointment_id=appointment_id,
            service_id=service_id
        )
    except (httpx.HTTPStatusError, RuntimeError) as api_error:
        await crud_client.delete_appointment(appointment_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al vincular el servicio: {str(api_error)}"
        )

@router.post("/customer/appointments", status_code=status.HTTP_201_CREATED)
async def customer_book_appointment(body: dict, current_user: dict = Depends(get_current_user)):
    """
    Confirma una reserva de cita para un cliente.
    Realiza todas las validaciones de disponibilidad y conflictos horaria.
    """
    barber_id = body.get("barber_id")
    service_id = body.get("service_id")
    appointment_date_str = body.get("appointment_date") # YYYY-MM-DD
    start_time_str = body.get("start_time") # HH:MM

    if not all([barber_id, service_id, appointment_date_str, start_time_str]):
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios.")

    # Get service duration
    service = await crud_client.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado.")
    duration_min = int(service["duration_minutes"])
    shop_id = service["barbershop_id"]

    # Parse inputs (SRP: Parsing responsibility)
    app_date, start_time, end_time = _parse_booking_request_times(
        appointment_date_str=appointment_date_str,
        start_time_str=start_time_str,
        duration_min=duration_min
    )

    # 1. Validate availability and overlaps (HU21 / HU28)
    # We call our validation function directly
    from app.controllers.appointment_controller import validate_appointment_rules
    await validate_appointment_rules(
        barbershop_id=shop_id,
        barber_id=barber_id,
        app_date=app_date,
        start_time=start_time,
        end_time=end_time
    )

    # 2. Create appointment
    new_appointment = await crud_client.create_appointment(
        barbershop_id=shop_id,
        client_id=current_user["id"],
        barber_id=barber_id,
        appointment_date=str(app_date),
        start_time=start_time.strftime("%H:%M:%S"),
        end_time=end_time.strftime("%H:%M:%S"),
        notes=body.get("notes")
    )

    # 3. Link service (SRP: Database transaction / rollback responsibility)
    await _link_service_with_rollback(
        appointment_id=new_appointment["id"],
        service_id=service_id
    )

    return {
        "status": "success",
        "message": "Cita agendada de forma correcta",
        "appointment_id": new_appointment["id"]
    }

@router.get("/customer/test-setup-availability")
async def test_setup_availability():
    """
    Ruta temporal de prueba para registrar bloques de disponibilidad para todos los barberos
    para todos los días de la semana (1 al 7) de 08:00 a 20:00.
    """
    try:
        # 1. Obtener todos los miembros
        members = await crud_client.list_members()
        barbers = [m for m in members if m.get("role") == "barber"]
        
        created = []
        for barber in barbers:
            barber_id = barber["user_id"]
            shop_id = barber["barbershop_id"]
            for day in range(1, 8):
                try:
                    # Check if already exists for this barber and day
                    existing = await crud_client.list_availabilities(barber_id=barber_id)
                    day_exists = any(av["day_of_week"] == day for av in existing)
                    if not day_exists:
                        av = await crud_client.create_availability(
                            barbershop_id=shop_id,
                            barber_id=barber_id,
                            day_of_week=day,
                            start_time="08:00:00",
                            end_time="20:00:00",
                            is_available=True
                        )
                        created.append(f"Creado: Barbero {barber_id} Dia {day}")
                    else:
                        created.append(f"Ya existe: Barbero {barber_id} Dia {day}")
                except Exception as e:
                    created.append(f"Error Barbero {barber_id} Dia {day}: {str(e)}")
        return {"status": "success", "message": "Disponibilidades configuradas", "details": created}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error configurando disponibilidades: {str(e)}")

