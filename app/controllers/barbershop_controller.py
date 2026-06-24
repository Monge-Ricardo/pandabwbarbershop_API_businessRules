from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.clients.crud_client import crud_client
from app.models.schemas.barbershop_schema import (
    BarbershopCreate, BarbershopUpdate, BarbershopResponse,
    MemberCreate, MemberUpdate, MemberResponse
)
from app.middleware.auth import get_current_user

router = APIRouter(tags=["Barbershops & Members"])

async def check_is_barbershop_owner(user_id: str, barbershop_id: str):
    """Verifica si el usuario es el dueño de la barbería."""
    memberships = await crud_client.list_members(barbershop_id=barbershop_id, user_id=user_id)
    if not memberships or not any(m["role"].upper() == "OWNER" for m in memberships):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restricción: Solo el Propietario (Owner) de la barbería puede realizar esta acción."
        )

# --- BARBERSHOP ENDPOINTS ---

@router.get("/barbershops", response_model=List[BarbershopResponse])
async def list_barbershops(current_user: dict = Depends(get_current_user)):
    """
    Lista todas las barberías registradas en la plataforma.
    """
    return await crud_client.list_barbershops()

@router.post("/barbershops", response_model=BarbershopResponse, status_code=status.HTTP_201_CREATED)
async def create_barbershop(body: BarbershopCreate, current_user: dict = Depends(get_current_user)):
    """
    Registra una nueva barbería. 
    Establece automáticamente al creador como el Propietario (Owner).
    """
    # Create the barbershop
    new_shop = await crud_client.create_barbershop(
        name=body.name,
        slug=body.slug,
        description=body.description,
        logo_url=body.logo_url,
        address=body.address,
        phone=body.phone,
        email=body.email
    )
    
    # Auto-assign owner membership
    try:
        await crud_client.create_member(
            barbershop_id=new_shop["id"],
            user_id=current_user["id"],
            role="owner",
            status="active"
        )
    except Exception as e:
        # Rollback creation if membership setup fails
        await crud_client.delete_barbershop(new_shop["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al asignar membresía de propietario: {str(e)}"
        )
        
    return new_shop

@router.get("/barbershops/{shop_id}", response_model=BarbershopResponse)
async def get_barbershop_details(shop_id: str, current_user: dict = Depends(get_current_user)):
    """
    Obtiene detalles específicos de una barbería.
    """
    shop = await crud_client.get_barbershop(shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbería no encontrada."
        )
    return shop

@router.put("/barbershops/{shop_id}", response_model=BarbershopResponse)
async def update_barbershop_details(shop_id: str, body: BarbershopUpdate, current_user: dict = Depends(get_current_user)):
    """
    Permite editar la información de la barbería. 
    Restringido al Propietario de la misma (HU26).
    """
    # Validate owner status
    await check_is_barbershop_owner(current_user["id"], shop_id)
    
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        shop = await crud_client.get_barbershop(shop_id)
        return shop

    return await crud_client.update_barbershop(shop_id, update_data)

@router.delete("/barbershops/{shop_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_barbershop_details(shop_id: str, current_user: dict = Depends(get_current_user)):
    """
    Elimina una barbería de la plataforma.
    Restringido al Propietario de la misma.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    await crud_client.delete_barbershop(shop_id)
    return None

# --- BARBERSHOP MEMBERS ENDPOINTS ---

@router.get("/barbershops/{shop_id}/members", response_model=List[MemberResponse])
async def list_barbershop_members(shop_id: str, current_user: dict = Depends(get_current_user)):
    """
    Lista todos los miembros (barberos / propietarios) vinculados a la barbería.
    """
    members = await crud_client.list_members(barbershop_id=shop_id)
    
    # Resolve names for response schema
    resolved_members = []
    for m in members:
        user_profile = await crud_client.get_user(m["user_id"])
        resolved_members.append({
            "member_id": m["id"],
            "user_id": m["user_id"],
            "name": user_profile["full_name"] if user_profile else "Usuario Desconocido",
            "role": m["role"],
            "status": m["status"],
            "joined_at": m["joined_at"]
        })
    return resolved_members

@router.post("/barbershops/{shop_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_barbershop_member(shop_id: str, body: MemberCreate, current_user: dict = Depends(get_current_user)):
    """
    Vincula un barbero o miembro a la barbería.
    Restringido al Propietario de la misma (HU10 / HU11).
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    
    # Verify user profile exists
    user = await crud_client.get_user(body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario que intenta agregar no tiene un perfil registrado."
        )

    new_member = await crud_client.create_member(
        barbershop_id=shop_id,
        user_id=body.user_id,
        role=body.role,
        status="active"
    )
    
    return {
        "member_id": new_member["id"],
        "user_id": new_member["user_id"],
        "name": user["full_name"],
        "role": new_member["role"],
        "status": new_member["status"],
        "joined_at": new_member["joined_at"]
    }

@router.get("/barbershops/{shop_id}/members/{member_id}", response_model=MemberResponse)
async def get_barbershop_member_details(shop_id: str, member_id: str, current_user: dict = Depends(get_current_user)):
    """
    Obtiene detalles de un miembro específico.
    """
    member = await crud_client.get_member(member_id)
    if not member or member["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado en esta barbería."
        )
        
    user = await crud_client.get_user(member["user_id"])
    return {
        "member_id": member["id"],
        "user_id": member["user_id"],
        "name": user["full_name"] if user else "Usuario Desconocido",
        "role": member["role"],
        "status": member["status"],
        "joined_at": member["joined_at"]
    }

@router.put("/barbershops/{shop_id}/members/{member_id}", response_model=MemberResponse)
async def update_barbershop_member(shop_id: str, member_id: str, body: MemberUpdate, current_user: dict = Depends(get_current_user)):
    """
    Modifica el rol o estado de un miembro.
    Restringido al Propietario de la barbería.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    
    member = await crud_client.get_member(member_id)
    if not member or member["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado."
        )

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        user = await crud_client.get_user(member["user_id"])
        return {
            "member_id": member["id"],
            "user_id": member["user_id"],
            "name": user["full_name"] if user else "",
            "role": member["role"],
            "status": member["status"],
            "joined_at": member["joined_at"]
        }

    updated = await crud_client.update_member(member_id, update_data)
    user = await crud_client.get_user(updated["user_id"])
    return {
        "member_id": updated["id"],
        "user_id": updated["user_id"],
        "name": user["full_name"] if user else "",
        "role": updated["role"],
        "status": updated["status"],
        "joined_at": updated["joined_at"]
    }

@router.delete("/barbershops/{shop_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_barbershop_member(shop_id: str, member_id: str, current_user: dict = Depends(get_current_user)):
    """
    Remueve a un miembro de la barbería.
    Restringido al Propietario de la barbería.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    
    member = await crud_client.get_member(member_id)
    if not member or member["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Miembro no encontrado."
        )

    await crud_client.delete_member(member_id)
    return None
