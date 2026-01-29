# src/services/validation.py (NEW FILE)
"""
FastAPI dependency for validating period inputs.
"""
from fastapi import HTTPException
from src.services.periods import canonicalize_period, is_yyyy_mm

def validate_period(month_year: str) -> str:
    """
    Validate and normalize period input.
    
    Args:
        month_year: User-provided period string
    
    Returns:
        Canonical 'YYYY-MM' string
    
    Raises:
        HTTPException(400) if invalid
    """
    if not month_year or not month_year.strip():
        raise HTTPException(
            status_code=400,
            detail="month_year is required"
        )
    
    canonical = canonicalize_period(month_year)
    if canonical is None:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid month format: {month_year}. Expected YYYY-MM or 'Month YYYY'"
        )
    
    # Additional sanity check
    if not is_yyyy_mm(canonical):
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: canonicalization produced invalid format: {canonical}"
        )
    
    return canonical