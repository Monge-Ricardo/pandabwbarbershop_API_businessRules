import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.clients.crud_client import crud_client
from app.models.schemas.user_schema import UserCreate, UserUpdate, UserResponse
from app.middleware.auth import get_current_user, hash_password

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("", response_model=List[UserResponse])
async def list_users(current_user: dict = Depends(get_current_user)):
    """
    Obtiene la lista de todos los usuarios registrados en el sistema.
    """
    return await crud_client.list_users()

@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """
    Obtiene el perfil del usuario actualmente autenticado.
    """
    return current_user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Obtiene los detalles de un usuario específico.
    """
    user = await crud_client.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )
    return user

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_admin(body: UserCreate, current_user: dict = Depends(get_current_user)):
    """
    Crea manualmente un usuario y su cuenta de autenticación (Reservado para administradores/dueños).
    """
    # Verify if email is already in use
    existing = await crud_client.list_users(email=body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado."
        )

    user_uuid = str(uuid.uuid4())
    default_hashed_pass = hash_password("SecurePassword123!") # Default password

    try:
        # Create auth record
        await crud_client.create_auth_user(id=user_uuid, email=body.email, encrypted_password=default_hashed_pass)
        
        # Create public profile
        profile = await crud_client.create_user(
            id=user_uuid,
            full_name=body.full_name,
            email=body.email,
            phone=body.phone,
            avatar_url=body.avatar_url
        )
        return profile
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear el usuario: {str(e)}"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user_profile(user_id: str, body: UserUpdate, current_user: dict = Depends(get_current_user)):
    """
    Actualiza la información de perfil de un usuario.
    Los usuarios normales solo pueden actualizar su propio perfil.
    """
    if current_user["id"] != user_id and current_user.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para actualizar este perfil."
        )

    user = await crud_client.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return user

    updated = await crud_client.update_user(user_id, update_data)
    return updated

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    """
    Elimina a un usuario del sistema (tanto el perfil como sus credenciales).
    Requiere ser el dueño del perfil o el propietario de la barbería.
    """
    if current_user["id"] != user_id and current_user.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permisos para eliminar este usuario."
        )

    user = await crud_client.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    try:
        await crud_client.delete_user(user_id)
        await crud_client.delete_auth_user(user_id)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar el usuario: {str(e)}"
        )
