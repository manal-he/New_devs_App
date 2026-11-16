from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from sqlalchemy import text
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user
from app.core.database_pool import db_pool

router = APIRouter()

@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user: dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    try:
        if not db_pool.session_factory:
            await db_pool.initialize()
        async with db_pool.get_session() as session:
            result = await session.execute(
                text("SELECT id, name, timezone FROM properties WHERE tenant_id = :tenant_id ORDER BY id"),
                {"tenant_id": tenant_id},
            )
            return [{"id": r.id, "name": r.name, "timezone": r.timezone} for r in result]
    except Exception:
        raise HTTPException(status_code=503, detail="Property list temporarily unavailable")

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")
    
    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Revenue data temporarily unavailable")
    
    total_revenue_float = float(revenue_data['total'])
    
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
