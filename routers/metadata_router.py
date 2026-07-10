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

    vibe_colors = {
        "AMBITIOUS": "rgb(10, 75, 92)",
        "PIZZA_CHILL": "rgb(224, 117, 43)",
        "MIND_BENDER": "rgb(112, 41, 184)",
        "ADRENALINE": "rgb(221, 28, 28)",
        "DATE_NIGHT": "rgb(194, 46, 108)",
        "DEEP_FEELS": "rgb(23, 42, 87)",
        "LAUGH_RIOT": "rgb(245, 199, 25)",
        "SPINE_CHILLING": "rgb(46, 64, 51)",
        "FAMILY_FUN": "rgb(38, 153, 224)",
        "INSPIRING": "rgb(227, 172, 54)",
        "EPIC_JOURNEY": "rgb(161, 113, 66)",
        "GUILTY_PLEASURE": "rgb(240, 98, 146)",
    }

    for vibe in vibes:
        if vibe not in vibe_colors:
            vibe_colors[vibe] = "rgb(0,0,0)"
    
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
        "eras": eras,
        "colors": vibe_colors
    }


@router.get("/interaction-statuses", summary="Available interaction statuses for movie buttons")
async def get_interaction_statuses():
    """
    Returns the list of valid interaction statuses.
    Frontend should use these as the only allowed button values.
    """
    return {"statuses": INTERACTION_STATUSES}
