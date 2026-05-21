"""
AgriGuard MVP Input Validator
=============================
This module ensures that farmer inputs are:
- Complete
- Reasonable
- Not obviously fake or corrupted

Designed for demo reliability (not over-engineered ML validation).
"""

from datetime import datetime


# =============================================================================
# VALID CROP LIST (MVP SCOPE)
# =============================================================================

VALID_CROPS = [
    "maize",
    "beans",
    "rice",
    "wheat",
    "cassava",
    "coffee",
    "bananas"
]


# =============================================================================
# VALIDATION FUNCTION
# =============================================================================

def validate_input(data: dict):
    """
    Validate farmer input before sending to ML model.

    Args:
        data (dict): user input

    Returns:
        dict: validation result
    """

    try:
        errors = []

        crop = data.get("crop")
        region = data.get("region")
        date = data.get("date")

        # ---------------------------------------------------------
        # 1. Missing field checks
        # ---------------------------------------------------------
        if not crop:
            errors.append("crop is required")

        if not region:
            errors.append("region is required")

        if not date:
            errors.append("date is required")

        # ---------------------------------------------------------
        # 2. Crop validation
        # ---------------------------------------------------------
        if crop and crop.lower() not in VALID_CROPS:
            errors.append(f"unsupported crop: {crop}")

        # ---------------------------------------------------------
        # 3. Basic fake input detection rules
        # ---------------------------------------------------------

        # unrealistic region name (too short or numeric)
        if region and (len(region) < 2 or region.isdigit()):
            errors.append("invalid region name")

        # unrealistic crop text injection check
        if crop and any(char.isdigit() for char in crop):
            errors.append("invalid crop format")

        # ---------------------------------------------------------
        # 4. Final decision
        # ---------------------------------------------------------
        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "is_fake": not is_valid,
            "errors": errors,
            "confidence": 1.0 if is_valid else 0.3,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "is_valid": False,
            "is_fake": True,
            "errors": ["validation system failure"],
            "detail": str(e),
            "confidence": 0.0,
            "timestamp": datetime.utcnow().isoformat()
        }


# =============================================================================
# QUICK HELPER (OPTIONAL USE IN ENDPOINTS)
# =============================================================================

def is_valid_input(data: dict) -> bool:
    """
    Simple boolean check for fast API usage.
    """
    return validate_input(data)["is_valid"]