from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from datetime import datetime, date, time, timedelta
from app.clients.crud_client import crud_client
from app.middleware.auth import get_current_user, require_role
from app.controllers.appointment_controller import parse_time_str, parse_date_str

router = APIRouter(prefix="/api", tags=["Role Dashboards (Owner, Barber, Customer)"])

# Helper to verify ownership of a shop
async def get_owner_barbershop_id(owner_id: str) -> str:
    memberships = await crud_client.list_members(user_id=owner_id)
    for m in memberships:
        if m["role"].upper() == "OWNER" and m["status"] == "active":
            return m["barbershop_id"]
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="El usuario actual no es propietario activo de ninguna barbería."
    )

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
# 👑 A. ENDPOINTS DEL DUEÑO (OWNER)
# ========================================================

@router.put("/owner/barbershop", dependencies=[Depends(require_role(["owner"]))])
async def owner_update_barbershop(body: dict, current_user: dict = Depends(get_current_user)):
    """
    Actualiza el perfil de la barbería del dueño autenticado.
    """
    shop_id = await get_owner_barbershop_id(current_user["id"])
    return await crud_client.update_barbershop(shop_id, body)

@router.post("/owner/barbers", dependencies=[Depends(require_role(["owner"]))])
async def owner_add_barber(body: dict, current_user: dict = Depends(get_current_user)):
    """
    Añade un barbero registrado a la barbería del dueño usando su correo electrónico.
    """
    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Se requiere el campo 'email'.")
        
    shop_id = await get_owner_barbershop_id(current_user["id"])
    
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
async def owner_patch_barber_status(member_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    """
    Cambia el estatus (active / inactive) de un miembro barbero.
    """
    new_status = body.get("status")
    if new_status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Estatus no válido. Use 'active' o 'inactive'.")
        
    shop_id = await get_owner_barbershop_id(current_user["id"])
    
    # Verify member exists and belongs to this shop
    member = await crud_client.get_member(member_id)
    if not member or member["barbershop_id"] != shop_id:
        raise HTTPException(status_code=404, detail="Miembro no encontrado en su barbería.")
        
    return await crud_client.update_member(member_id, {"status": new_status})

@router.get("/owner/appointments", dependencies=[Depends(require_role(["owner"]))])
async def owner_list_appointments(
    date: Optional[str] = None,
    barber_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Filtra citas de la barbería del dueño activo.
    """
    shop_id = await get_owner_barbershop_id(current_user["id"])
    return await crud_client.list_appointments(
        barbershop_id=shop_id,
        barber_id=barber_id,
        appointment_date=date
    )

@router.patch("/owner/appointments/{appointment_id}/status", dependencies=[Depends(require_role(["owner"]))])
async def owner_patch_appointment_status(appointment_id: str, body: dict, current_user: dict = Depends(get_current_user)):
    """
    Modifica el estado de una cita (pending, confirmed, cancelled).
    """
    new_status = body.get("status")
    if new_status not in ["pending", "confirmed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Estado no válido.")
        
    shop_id = await get_owner_barbershop_id(current_user["id"])
    
    # Verify appointment belongs to owner's shop
    app = await crud_client.get_appointment(appointment_id)
    if not app or app["barbershop_id"] != shop_id:
        raise HTTPException(status_code=404, detail="Cita no encontrada en su barbería.")
        
    return await crud_client.update_appointment(appointment_id, {"status": new_status})

# ========================================================
# 💈 B. ENDPOINTS DEL BARBERO (BARBER)
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
# 👥 C. ENDPOINTS DEL CLIENTE (CUSTOMER)
# ========================================================

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
    matching_av = None
    for av in availabilities:
        if av["day_of_week"] == day_of_week and av["is_available"]:
            matching_av = av
            break
            
    if not matching_av:
        return {"date": date, "available_slots": []}

    av_start = parse_time_str(matching_av["start_time"])
    av_end = parse_time_str(matching_av["end_time"])

    # 4. Fetch existing appointments
    appointments = await crud_client.list_appointments(barber_id=barber_id, appointment_date=date)
    active_appointments = [a for a in appointments if a["status"] != "cancelled"]

    # 5. Generate slots at 30-minute intervals
    start_dt = datetime.combine(query_date, av_start)
    end_dt = datetime.combine(query_date, av_end)
    
    slots = []
    current_dt = start_dt
    while current_dt + duration <= end_dt:
        slot_start = current_dt.time()
        slot_end = (current_dt + duration).time()
        
        # Check overlaps
        overlap = False
        for app in active_appointments:
            app_start = parse_time_str(app["start_time"])
            app_end = parse_time_str(app["end_time"])
            
            # overlap check
            if slot_start < app_end and app_start < slot_end:
                overlap = True
                break
                
        if not overlap:
            slots.append(slot_start.strftime("%H:%M"))
            
        current_dt += timedelta(minutes=30) # 30 min intervals to choose from

    return {
        "date": date,
        "available_slots": slots
    }

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

    # Parse inputs
    try:
        app_date = datetime.strptime(appointment_date_str, "%Y-%m-%d").date()
        parts = start_time_str.split(":")
        start_time = time(int(parts[0]), int(parts[1]))
        
        # Calculate end time based on service duration
        temp_dt = datetime.combine(app_date, start_time) + timedelta(minutes=duration_min)
        end_time = temp_dt.time()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al parsear fecha u hora: {str(e)}")

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
    new_app = await crud_client.create_appointment(
        barbershop_id=shop_id,
        client_id=current_user["id"],
        barber_id=barber_id,
        appointment_date=str(app_date),
        start_time=start_time.strftime("%H:%M:%S"),
        end_time=end_time.strftime("%H:%M:%S"),
        notes=body.get("notes")
    )

    # 3. Link service
    try:
        await crud_client.create_appointment_service(
            appointment_id=new_app["id"],
            service_id=service_id
        )
    except Exception as e:
        # Rollback
        await crud_client.delete_appointment(new_app["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al vincular el servicio: {str(e)}"
        )

    return {
        "status": "success",
        "message": "Cita agendada de forma correcta",
        "appointment_id": new_app["id"]
    }
