import uuid
import httpx
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
from app.clients.crud_client import crud_client
from app.models.schemas.auth_schema import RegisterRequest, LoginRequest, TokenResponse, GoogleLoginRequest
from app.middleware.auth import hash_password, verify_password, create_access_token, get_current_user, resolve_user_role
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from app.config import settings

router = APIRouter(tags=["Authentication & Sessions"])

mail_conf = ConnectionConfig(
    MAIL_USERNAME = settings.MAIL_USERNAME,
    MAIL_PASSWORD = settings.MAIL_PASSWORD,
    MAIL_FROM = settings.MAIL_FROM,
    MAIL_PORT = settings.MAIL_PORT,
    MAIL_SERVER = settings.MAIL_SERVER,
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """
    Registra un nuevo usuario en la plataforma.
    Primero crea las credenciales en auth_users, luego crea el perfil en public_users.
    """
    # Check if user already exists
    existing = await crud_client.list_users(email=body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado."
        )

    user_uuid = str(uuid.uuid4())
    hashed_pass = hash_password(body.password)

    try:
        # 1. Create entry in auth schema
        await crud_client.create_auth_user(id=user_uuid, email=body.email, encrypted_password=hashed_pass)
        
        # 2. Create profile in public schema
        profile = await crud_client.create_user(id=user_uuid, full_name=body.name, email=body.email)
        
        # Send welcome email asynchronously
        try:
            html_content = f"""
            <html>
              <body style="font-family: Arial, sans-serif; background-color: #111; color: #fff; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background-color: #1a1a1a; padding: 30px; border-radius: 8px; border: 1px solid #D4AF37;">
                  <h2 style="color: #D4AF37; text-align: center;">¡Hola, {body.name}!</h2>
                  <p style="font-size: 16px; line-height: 1.5; color: #eee;">Te damos la bienvenida a <strong>Panda BW Barbershop</strong>.</p>
                  <p style="font-size: 14px; color: #ccc;">Tu cuenta ha sido creada exitosamente con el correo: <strong>{body.email}</strong>.</p>
                  <p style="font-size: 14px; color: #ccc;">Ya puedes iniciar sesión en la aplicación para reservar tu primer servicio.</p>
                  <hr style="border: 0; border-top: 1px solid #D4AF37; margin: 20px 0;" />
                  <p style="font-size: 12px; text-align: center; color: #888;">Atentamente,<br/>El equipo de Panda BW Barbershop</p>
                </div>
              </body>
            </html>
            """
            message = MessageSchema(
                subject="¡Bienvenido a Panda BW Barbershop!",
                recipients=[body.email],
                body=html_content,
                subtype=MessageType.html
            )
            fm = FastMail(mail_conf)
            await fm.send_message(message)
        except Exception as mail_err:
            print(f"Error al enviar correo de bienvenida: {mail_err}")
        
        return {
            "message": "Usuario registrado exitosamente",
            "user": {
                "id": profile["id"],
                "name": profile["full_name"],
                "email": profile["email"]
            }
        }
    except Exception as e:
        # Try cleaning up in case of failure
        try:
            await crud_client.delete_auth_user(user_uuid)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante el registro: {str(e)}"
        )

@router.post("/auth/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """
    Inicia sesión de un usuario y devuelve un token de acceso JWT.
    """
    auth_user = await crud_client.get_auth_user_by_email(body.email)
    if not auth_user or not verify_password(body.password, auth_user["encrypted_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas."
        )

    # Resolve details
    public_profile = await crud_client.get_user(auth_user["id"])
    role = await resolve_user_role(auth_user["id"])
    
    # Resolve barbershop_id if user has memberships
    barbershop_id = None
    memberships = await crud_client.list_members(user_id=auth_user["id"])
    if memberships:
        barbershop_id = memberships[0]["barbershop_id"]

    # Generate token
    token = create_access_token(data={"sub": auth_user["id"], "role": role})

    return {
        "message": "Sesión iniciada correctamente",
        "token": token,
        "user": {
            "id": auth_user["id"],
            "name": public_profile["full_name"] if public_profile else "",
            "email": auth_user["email"],
            "barbershop_id": barbershop_id
        }
    }

# Sessions mappings matching URIS.md
@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(body: LoginRequest):
    """
    Crea una sesión (Login de API).
    """
    res = await login(body)
    return {
        "token": res["token"],
        "expires_at": None  # Managed client side or default 7 days expiration
    }

@router.get("/sessions/current")
async def current_session(current_user: dict = Depends(get_current_user)):
    """
    Consulta la sesión actual activa.
    """
    return {
        "user_id": current_user["id"],
        "full_name": current_user["full_name"],
        "session_active": True
    }

@router.delete("/sessions/current", status_code=status.HTTP_204_NO_CONTENT)
async def destroy_session(current_user: dict = Depends(get_current_user)):
    """
    Cierra la sesión actual (Logout).
    """
    # For a JWT implementation, invalidation happens on the client side (discarding the token).
    return None

@router.post("/auth/google", response_model=TokenResponse)
async def google_auth(body: GoogleLoginRequest):
    """
    Autentica a un usuario mediante Google OAuth (Bridge).
    Valida el id_token con la API de Google, registra al usuario si no existe,
    y devuelve un token de acceso JWT del sistema.
    """
    token_info_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={body.id_token}"
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(token_info_url, timeout=5.0)
            if res.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token de Google inválido o expirado."
                )
            payload = res.json()
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No se pudo conectar con el servicio de autenticación de Google: {str(exc)}"
            )

    email = payload.get("email")
    name = payload.get("name", "Usuario de Google")
    
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de Google no contiene un correo electrónico."
        )

    # Check if user already exists in auth schema
    auth_user = await crud_client.get_auth_user_by_email(email)
    
    if auth_user:
        user_uuid = auth_user["id"]
        # Check if they have a public profile, if not, create it
        user_profile = await crud_client.get_user(user_uuid)
        if not user_profile:
            user_profile = await crud_client.create_user(id=user_uuid, full_name=name, email=email)
    else:
        # Check if they exist in public schema (in case of orphan profile)
        existing_public = await crud_client.list_users(email=email)
        if existing_public:
            user_profile = existing_public[0]
            user_uuid = user_profile["id"]
            
            # Create auth credentials since they have profile but no credentials
            random_pass = str(uuid.uuid4())
            hashed_pass = hash_password(random_pass)
            try:
                await crud_client.create_auth_user(id=user_uuid, email=email, encrypted_password=hashed_pass)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error vinculando credenciales de autenticación: {str(e)}"
                )
        else:
            # Create completely new user
            user_uuid = str(uuid.uuid4())
            random_pass = str(uuid.uuid4())
            hashed_pass = hash_password(random_pass)
            
            try:
                # 1. Create credentials in auth schema
                await crud_client.create_auth_user(id=user_uuid, email=email, encrypted_password=hashed_pass)
                # 2. Create profile in public schema
                user_profile = await crud_client.create_user(id=user_uuid, full_name=name, email=email)
            except Exception as e:
                # Clean up auth credentials on failure
                try:
                    await crud_client.delete_auth_user(user_uuid)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error durante el registro automático con Google: {str(e)}"
                )

    # Resolve role (defaults to customer if no barbershop memberships exist)
    role = await resolve_user_role(user_uuid)
    
    # Resolve barbershop_id if user has memberships
    barbershop_id = None
    memberships = await crud_client.list_members(user_id=user_uuid)
    if memberships:
        barbershop_id = memberships[0]["barbershop_id"]

    # Generate our local system token
    token = create_access_token(data={"sub": user_uuid, "role": role})
    
    return {
        "message": "Sesión iniciada correctamente con Google",
        "token": token,
        "user": {
            "id": user_uuid,
            "name": user_profile.get("full_name") or name,
            "email": email,
            "barbershop_id": barbershop_id
        }
    }
