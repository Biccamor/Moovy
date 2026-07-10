from fastapi import APIRouter
from schemas.schemas import INTERACTION_STATUSES

router = APIRouter(prefix="/metadata", tags=["Metadata"])

@router.get("/preferences-options")
async def get_preferences_options():
    """
    Returns available movie genres and eras for the preferences selection.
    """
    vibes = [
        "AMBITIOUS",
        "PIZZA_CHILL",
        "MIND_BENDER",
        "ADRENALINE",
        "DATE_NIGHT",
        "DEEP_FEELS",
        "LAUGH_RIOT",
        "SPINE_CHILLING",
        "FAMILY_FUN",
        "INSPIRING",
        "EPIC_JOURNEY",
        "GUILTY_PLEASURE"
    ]
    
    eras = [
        'Klasyka (przed 80.)',
        'Lata 80.',
        'Lata 90.',
        'Lata 00.',
        'Lata 10.',
        'Nowości (Lata 20.)'
    ]
    
    return {
        "vibes": vibes,
        "eras": eras
    }


@router.get("/interaction-statuses", summary="Available interaction statuses for movie buttons")
async def get_interaction_statuses():
    """
    Returns the list of valid interaction statuses.
    Frontend should use these as the only allowed button values.
    """
    return {"statuses": INTERACTION_STATUSES}
