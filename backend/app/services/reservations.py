from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo

async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Decimal:
    """
    Calculates revenue for a calendar month in the PROPERTY'S local time zone.
    """
    from sqlalchemy import text
    from app.core.database_pool import db_pool

    if not db_pool.session_factory:
        await db_pool.initialize()

    async with db_pool.get_session() as session:
        prop = (await session.execute(
            text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
            {"property_id": property_id, "tenant_id": tenant_id},
        )).fetchone()
        if not prop:
            raise ValueError("Property not found for this tenant")

        # Month boundaries at local midnight (e.g. Europe/Paris), not UTC
        tz = ZoneInfo(prop.timezone)
        start_date = datetime(year, month, 1, tzinfo=tz)
        end_date = datetime(year + 1, 1, 1, tzinfo=tz) if month == 12 else datetime(year, month + 1, 1, tzinfo=tz)

        total = (await session.execute(
            text("""
                SELECT COALESCE(SUM(total_amount), 0)
                FROM reservations
                WHERE property_id = :property_id
                  AND tenant_id = :tenant_id
                  AND check_in_date >= :start_date
                  AND check_in_date < :end_date
            """),
            {"property_id": property_id, "tenant_id": tenant_id,
             "start_date": start_date, "end_date": end_date},
        )).scalar()

        return Decimal(str(total))

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import DatabasePool
        
        # Initialize pool if needed
        db_pool = DatabasePool()
        await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        # Never return invented revenue figures to a client: fail loudly instead.
        raise
