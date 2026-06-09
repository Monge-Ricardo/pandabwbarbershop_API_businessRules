import random
import string
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime
from app.clients.crud_client import crud_client
from app.models.schemas.invitation_schema import InvitationCreate, InvitationResponse
from app.middleware.auth import get_current_user
from app.controllers.barbershop_controller import check_is_barbershop_owner

router = APIRouter(prefix="/barbershops", tags=["Invitations"])

def generate_invitation_code() -> str:
    """Generates a random code like SH-982-XYZ."""
    p1 = "".join(random.choices(string.digits, k=3))
    p2 = "".join(random.choices(string.ascii_uppercase, k=3))
    return f"SH-{p1}-{p2}"

@router.get("/{shop_id}/invitations", response_model=List[InvitationResponse])
async def list_invitations(shop_id: str, current_user: dict = Depends(get_current_user)):
    """
    Lista todos los códigos de invitación generados para la barbería.
    Restringido al Propietario (HU10).
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    raw_codes = await crud_client.list_invitation_codes(barbershop_id=shop_id)
    return [
        {
            "invitation_id": c["id"],
            "code": c["code"],
            "expires_at": datetime.fromisoformat(c["expires_at"].replace("Z", "+00:00")) if c["expires_at"] else None,
            "is_active": c["is_active"]
        }
        for c in raw_codes
    ]

@router.post("/{shop_id}/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(shop_id: str, body: InvitationCreate, current_user: dict = Depends(get_current_user)):
    """
    Genera un nuevo código de invitación para barberos.
    Restringido al Propietario.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)

    code = generate_invitation_code()
    
    expires_str = body.expires_at.isoformat() if body.expires_at else None

    new_code = await crud_client.create_invitation_code(
        barbershop_id=shop_id,
        code=code,
        expires_at=expires_str,
        is_active=True
    )

    return {
        "invitation_id": new_code["id"],
        "code": new_code["code"],
        "expires_at": datetime.fromisoformat(new_code["expires_at"].replace("Z", "+00:00")) if new_code["expires_at"] else None,
        "is_active": new_code["is_active"]
    }

@router.get("/{shop_id}/invitations/{invitation_id}", response_model=InvitationResponse)
async def get_invitation_details(shop_id: str, invitation_id: str, current_user: dict = Depends(get_current_user)):
    """
    Obtiene los detalles de un código de invitación.
    Restringido al Propietario.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    code = await crud_client.get_invitation_code(invitation_id)
    if not code or code["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código de invitación no encontrado."
        )
    return {
        "invitation_id": code["id"],
        "code": code["code"],
        "expires_at": datetime.fromisoformat(code["expires_at"].replace("Z", "+00:00")) if code["expires_at"] else None,
        "is_active": code["is_active"]
    }

@router.put("/{shop_id}/invitations/{invitation_id}", response_model=InvitationResponse)
async def update_invitation_status(shop_id: str, invitation_id: str, current_user: dict = Depends(get_current_user)):
    """
    Desactiva o modifica el estado de un código de invitación.
    Restringido al Propietario.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    code = await crud_client.get_invitation_code(invitation_id)
    if not code or code["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código de invitación no encontrado."
        )

    # Toggle active status or just set active to false
    updated = await crud_client.update_invitation_code(invitation_id, {"is_active": not code["is_active"]})
    return {
        "invitation_id": updated["id"],
        "code": updated["code"],
        "expires_at": datetime.fromisoformat(updated["expires_at"].replace("Z", "+00:00")) if updated["expires_at"] else None,
        "is_active": updated["is_active"]
    }

@router.delete("/{shop_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invitation(shop_id: str, invitation_id: str, current_user: dict = Depends(get_current_user)):
    """
    Elimina o revoca un código de invitación.
    Restringido al Propietario.
    """
    await check_is_barbershop_owner(current_user["id"], shop_id)
    code = await crud_client.get_invitation_code(invitation_id)
    if not code or code["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Código de invitación no encontrado."
        )

    await crud_client.delete_invitation_code(invitation_id)
    return None
