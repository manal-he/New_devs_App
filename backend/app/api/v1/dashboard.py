from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List
from sqlalchemy import text
from app.services.cache import get_revenue_summary
from app.services.reservations import calculate_monthly_revenue
from app.core.auth import authenticate_request as get_current_user
from app.core.database_pool import db_pool

from decimal import Decimal, ROUND_HALF_UP

router = APIRouter()

CENT = Decimal("0.01")

def to_money(value) -> str:
    """Round once, with Decimal, to cents (half-up). Never pass money through float."""
    return str(Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP))

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

@router.get("/dashboard/monthly")
async def get_dashboard_monthly(
    property_id: str,
    month: int = Query(..., ge=1, le=12),
    year: int = Query(..., ge=2000, le=2100),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")
    try:
        total = await calculate_monthly_revenue(property_id, tenant_id, month, year)
    except ValueError:
        raise HTTPException(status_code=404, detail="Property not found")
    except Exception:
        raise HTTPException(status_code=503, detail="Revenue data temporarily unavailable")
    return {"property_id": property_id, "month": month, "year": year,
            "total_revenue": to_money(total), "currency": "USD"}

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
    
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": to_money(revenue_data['total']),
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
