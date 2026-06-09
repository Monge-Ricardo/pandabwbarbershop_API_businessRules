import httpx
from typing import Dict, Any, List, Optional
from app.config import settings

class CrudClient:
    def __init__(self, base_url: str = settings.DATABASE_API_URL):
        self.base_url = base_url

    async def _request(self, method: str, path: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(method, url, json=json, params=params, timeout=10.0)
                if response.status_code == 404:
                    return None
                if response.status_code >= 400:
                    detail = response.json().get("detail", "Error en API de Datos") if response.content else "Error en API de Datos"
                    # We raise a custom exception containing the actual error message
                    raise httpx.HTTPStatusError(detail, request=response.request, response=response)
                if response.status_code == 204:
                    return None
                return response.json()
            except httpx.RequestError as exc:
                raise RuntimeError(f"Error de red al conectar al API de datos ({url}): {exc}")

    # --- AUTH USERS ---
    async def get_auth_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/auth-users/{user_id}")

    async def get_auth_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/auth-users/email/{email}")

    async def create_auth_user(self, id: str, email: str, encrypted_password: str) -> Dict[str, Any]:
        data = {"id": id, "email": email, "encrypted_password": encrypted_password}
        return await self._request("POST", "/auth-users", json=data)

    async def update_auth_user(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/auth-users/{user_id}", json=data)

    async def delete_auth_user(self, user_id: str) -> None:
        await self._request("DELETE", f"/auth-users/{user_id}")

    # --- PUBLIC USERS ---
    async def list_users(self, email: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"email": email} if email else None
        return await self._request("GET", "/users", params=params)

    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/users/{user_id}")

    async def create_user(self, id: str, full_name: str, email: str, phone: Optional[str] = None, avatar_url: Optional[str] = None) -> Dict[str, Any]:
        data = {"id": id, "full_name": full_name, "email": email, "phone": phone, "avatar_url": avatar_url}
        return await self._request("POST", "/users", json=data)

    async def update_user(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/users/{user_id}", json=data)

    async def delete_user(self, user_id: str) -> None:
        await self._request("DELETE", f"/users/{user_id}")

    # --- BARBERSHOPS ---
    async def list_barbershops(self, slug: Optional[str] = None, invite_code: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if slug:
            params["slug"] = slug
        if invite_code:
            params["invite_code"] = invite_code
        return await self._request("GET", "/barbershops", params=params)

    async def get_barbershop(self, shop_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/barbershops/{shop_id}")

    async def get_barbershop_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/barbershops/slug/{slug}")

    async def create_barbershop(self, name: str, slug: str, description: Optional[str] = None, logo_url: Optional[str] = None, address: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        data = {"name": name, "slug": slug, "description": description, "logo_url": logo_url, "address": address, "phone": phone, "email": email}
        return await self._request("POST", "/barbershops", json=data)

    async def update_barbershop(self, shop_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/barbershops/{shop_id}", json=data)

    async def delete_barbershop(self, shop_id: str) -> None:
        await self._request("DELETE", f"/barbershops/{shop_id}")

    # --- BARBERSHOP MEMBERS ---
    async def list_members(self, barbershop_id: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if barbershop_id:
            params["barbershop_id"] = barbershop_id
        if user_id:
            params["user_id"] = user_id
        return await self._request("GET", "/barbershop-members", params=params)

    async def get_member(self, member_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/barbershop-members/{member_id}")

    async def create_member(self, barbershop_id: str, user_id: str, role: str, status: str = "active") -> Dict[str, Any]:
        data = {"barbershop_id": barbershop_id, "user_id": user_id, "role": role, "status": status}
        return await self._request("POST", "/barbershop-members", json=data)

    async def update_member(self, member_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/barbershop-members/{member_id}", json=data)

    async def delete_member(self, member_id: str) -> None:
        await self._request("DELETE", f"/barbershop-members/{member_id}")

    # --- SERVICES ---
    async def list_services(self, barbershop_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"barbershop_id": barbershop_id} if barbershop_id else None
        return await self._request("GET", "/services", params=params)

    async def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/services/{service_id}")

    async def create_service(self, barbershop_id: str, name: str, description: Optional[str], price: float, duration_minutes: int) -> Dict[str, Any]:
        data = {"barbershop_id": barbershop_id, "name": name, "description": description, "price": price, "duration_minutes": duration_minutes}
        return await self._request("POST", "/services", json=data)

    async def update_service(self, service_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/services/{service_id}", json=data)

    async def delete_service(self, service_id: str) -> None:
        await self._request("DELETE", f"/services/{service_id}")

    # --- PRODUCTS ---
    async def list_products(self, barbershop_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"barbershop_id": barbershop_id} if barbershop_id else None
        return await self._request("GET", "/products", params=params)

    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/products/{product_id}")

    async def create_product(self, barbershop_id: str, name: str, description: Optional[str], price: float, stock: int, image_url: Optional[str]) -> Dict[str, Any]:
        data = {"barbershop_id": barbershop_id, "name": name, "description": description, "price": price, "stock": stock, "image_url": image_url}
        return await self._request("POST", "/products", json=data)

    async def update_product(self, product_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/products/{product_id}", json=data)

    async def delete_product(self, product_id: str) -> None:
        await self._request("DELETE", f"/products/{product_id}")

    # --- APPOINTMENTS ---
    async def list_appointments(self, barbershop_id: Optional[str] = None, client_id: Optional[str] = None, barber_id: Optional[str] = None, appointment_date: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if barbershop_id:
            params["barbershop_id"] = barbershop_id
        if client_id:
            params["client_id"] = client_id
        if barber_id:
            params["barber_id"] = barber_id
        if appointment_date:
            params["appointment_date"] = appointment_date
        return await self._request("GET", "/appointments", params=params)

    async def get_appointment(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/appointments/{appointment_id}")

    async def create_appointment(self, barbershop_id: str, client_id: str, barber_id: str, appointment_date: str, start_time: str, end_time: str, notes: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "barbershop_id": barbershop_id,
            "client_id": client_id,
            "barber_id": barber_id,
            "appointment_date": appointment_date,
            "start_time": start_time,
            "end_time": end_time,
            "notes": notes
        }
        return await self._request("POST", "/appointments", json=data)

    async def update_appointment(self, appointment_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/appointments/{appointment_id}", json=data)

    async def delete_appointment(self, appointment_id: str) -> None:
        await self._request("DELETE", f"/appointments/{appointment_id}")

    # --- APPOINTMENT SERVICES ---
    async def list_appointment_services(self, appointment_id: Optional[str] = None, service_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if appointment_id:
            params["appointment_id"] = appointment_id
        if service_id:
            params["service_id"] = service_id
        return await self._request("GET", "/appointment-services", params=params)

    async def get_appointment_service(self, relation_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/appointment-services/{relation_id}")

    async def create_appointment_service(self, appointment_id: str, service_id: str) -> Dict[str, Any]:
        data = {"appointment_id": appointment_id, "service_id": service_id}
        return await self._request("POST", "/appointment-services", json=data)

    async def delete_appointment_service(self, relation_id: str) -> None:
        await self._request("DELETE", f"/appointment-services/{relation_id}")

    async def delete_appointment_service_by_ids(self, appointment_id: str, service_id: str) -> None:
        await self._request("DELETE", f"/appointment-services/appointment/{appointment_id}/service/{service_id}")

    # --- AVAILABILITY ---
    async def list_availabilities(self, barber_id: Optional[str] = None, barbershop_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if barber_id:
            params["barber_id"] = barber_id
        if barbershop_id:
            params["barbershop_id"] = barbershop_id
        return await self._request("GET", "/availabilities", params=params)

    async def get_availability(self, availability_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/availabilities/{availability_id}")

    async def create_availability(self, barbershop_id: str, barber_id: str, day_of_week: int, start_time: str, end_time: str, is_available: bool = True) -> Dict[str, Any]:
        data = {
            "barbershop_id": barbershop_id,
            "barber_id": barber_id,
            "day_of_week": day_of_week,
            "start_time": start_time,
            "end_time": end_time,
            "is_available": is_available
        }
        return await self._request("POST", "/availabilities", json=data)

    async def update_availability(self, availability_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/availabilities/{availability_id}", json=data)

    async def delete_availability(self, availability_id: str) -> None:
        await self._request("DELETE", f"/availabilities/{availability_id}")

    # --- INVITATION CODES ---
    async def list_invitation_codes(self, barbershop_id: Optional[str] = None, code: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if barbershop_id:
            params["barbershop_id"] = barbershop_id
        if code:
            params["code"] = code
        return await self._request("GET", "/invitation-codes", params=params)

    async def get_invitation_code(self, code_id: str) -> Optional[Dict[str, Any]]:
        return await self._request("GET", f"/invitation-codes/{code_id}")

    async def create_invitation_code(self, barbershop_id: str, code: str, expires_at: Optional[str] = None, is_active: bool = True) -> Dict[str, Any]:
        data = {
            "barbershop_id": barbershop_id,
            "code": code,
            "expires_at": expires_at,
            "is_active": is_active
        }
        return await self._request("POST", "/invitation-codes", json=data)

    async def update_invitation_code(self, code_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return await self._request("PUT", f"/invitation-codes/{code_id}", json=data)

    async def delete_invitation_code(self, code_id: str) -> None:
        await self._request("DELETE", f"/invitation-codes/{code_id}")

crud_client = CrudClient()
