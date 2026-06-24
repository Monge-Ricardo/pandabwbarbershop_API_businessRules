from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from app.clients.crud_client import crud_client
from app.models.schemas.product_schema import ProductCreate, ProductUpdate, ProductResponse
from app.middleware.auth import get_current_user
from app.controllers.service_controller import check_is_barbershop_member

router = APIRouter(tags=["Products"])

@router.get("/barbershops/{shop_id}/products", response_model=List[ProductResponse])
async def list_shop_products(shop_id: str, current_user: dict = Depends(get_current_user)):
    """
    Obtiene la lista de productos de una barbería específica (HU19).
    """
    # Verify if shop exists
    shop = await crud_client.get_barbershop(shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbería no encontrada."
        )

    products = await crud_client.list_products(barbershop_id=shop_id)
    return [
        {
            "product_id": p["id"],
            "name": p["name"],
            "stock": p["stock"] or 0,
            "price": float(p["price"]) if p["price"] is not None else 0.0,
            "description": p["description"],
            "image_url": p["image_url"],
            "is_active": p["is_active"],
            "barbershop_id": p["barbershop_id"]
        }
        for p in products
    ]

@router.post("/barbershops/{shop_id}/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(shop_id: str, body: ProductCreate, current_user: dict = Depends(get_current_user)):
    """
    Registra un producto en el inventario de la barbería.
    Solo miembros (Barberos o Dueños) autorizados pueden crearlo (HU16).
    """
    if body.barbershop_id != shop_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El ID de la barbería en la ruta no coincide con el del cuerpo."
        )

    shop = await crud_client.get_barbershop(shop_id)
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Barbería no encontrada."
        )

    # Enforce membership check
    await check_is_barbershop_member(current_user["id"], shop_id)

    new_product = await crud_client.create_product(
        barbershop_id=shop_id,
        name=body.name,
        description=body.description,
        price=body.price,
        stock=body.stock,
        image_url=body.image_url
    )
    
    return {
        "product_id": new_product["id"],
        "name": new_product["name"],
        "stock": new_product["stock"] or 0,
        "price": float(new_product["price"]) if new_product["price"] is not None else 0.0,
        "description": new_product["description"],
        "image_url": new_product["image_url"],
        "is_active": new_product["is_active"],
        "barbershop_id": new_product["barbershop_id"]
    }

@router.get("/barbershops/{shop_id}/products/{product_id}", response_model=ProductResponse)
async def get_product_details(shop_id: str, product_id: str):
    """
    Obtiene detalles de un producto específico.
    """
    product = await crud_client.get_product(product_id)
    if not product or product["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado en esta barbería."
        )
    return {
        "product_id": product["id"],
        "name": product["name"],
        "stock": product["stock"] or 0,
        "price": float(product["price"]) if product["price"] is not None else 0.0,
        "description": product["description"],
        "image_url": product["image_url"],
        "is_active": product["is_active"],
        "barbershop_id": product["barbershop_id"]
    }

@router.put("/barbershops/{shop_id}/products/{product_id}", response_model=ProductResponse)
async def update_product_details(shop_id: str, product_id: str, body: ProductUpdate, current_user: dict = Depends(get_current_user)):
    """
    Actualiza el stock, precio u otros datos del producto.
    Solo miembros (Barberos o Dueños) autorizados pueden editarlo (HU17).
    """
    # Enforce membership check
    await check_is_barbershop_member(current_user["id"], shop_id)

    product = await crud_client.get_product(product_id)
    if not product or product["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado en esta barbería."
        )

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return {
            "product_id": product["id"],
            "name": product["name"],
            "stock": product["stock"] or 0,
            "price": float(product["price"]) if product["price"] is not None else 0.0,
            "description": product["description"],
            "image_url": product["image_url"],
            "is_active": product["is_active"],
            "barbershop_id": product["barbershop_id"]
        }

    updated = await crud_client.update_product(product_id, update_data)
    return {
        "product_id": updated["id"],
        "name": updated["name"],
        "stock": updated["stock"] or 0,
        "price": float(updated["price"]) if updated["price"] is not None else 0.0,
        "description": updated["description"],
        "image_url": updated["image_url"],
        "is_active": updated["is_active"],
        "barbershop_id": updated["barbershop_id"]
    }

@router.delete("/barbershops/{shop_id}/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_details(shop_id: str, product_id: str, current_user: dict = Depends(get_current_user)):
    """
    Elimina un producto del catálogo.
    Solo miembros (Barberos o Dueños) autorizados pueden eliminarlo (HU18).
    """
    # Enforce membership check
    await check_is_barbershop_member(current_user["id"], shop_id)

    product = await crud_client.get_product(product_id)
    if not product or product["barbershop_id"] != shop_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado en esta barbería."
        )

    await crud_client.delete_product(product_id)
    return None
