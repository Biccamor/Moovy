import pytest
from unittest.mock import MagicMock
from engine.recommendation_service import RecomService
from schemas.schemas import MovieSession, MovieSessionUser, Preferences
from uuid import uuid4

def test_vector_normalization_guilty_vs_thriller():
    # Tworzymy preferencje dla GuiltyUser (tylko GUILTY_PLEASURE - 1 vibe)
    user_guilty = MovieSessionUser(
        user_id=str(uuid4()),
        user_name="GuiltyUser",
        personal_vibe=Preferences(
            vibes=["GUILTY_PLEASURE"],
            hard_nos=[],
            max_runtime=120,
            allow_seen=False,
            eras=[]
        )
    )

    # Tworzymy preferencje dla ThrillerUser (4 vibes thriller/horror)
    user_thriller = MovieSessionUser(
        user_id=str(uuid4()),
        user_name="ThrillerUser",
        personal_vibe=Preferences(
            vibes=["SPINE_CHILLING", "MIND_BENDER", "ADRENALINE", "EXISTENTIAL"],
            hard_nos=[],
            max_runtime=120,
            allow_seen=False,
            eras=[]
        )
    )

    meta_data = MovieSession(
        host_id=user_guilty.user_id,
        session_id=str(uuid4()),
        invite_code="NORM12",
        meeting_type="RANDKA",
        users=[user_guilty, user_thriller]
    )

    session_mock = MagicMock()
    service = RecomService(meta_data, session_mock)

    # Generujemy prompty i wagi dla gatunków z RecomService
    prompts_with_weights = service._create_user_prompts()
    
    # Sprawdzamy wygenerowane wagi w prompts_with_weights.
    # Wkład każdego użytkownika w sumie wektora cech (gatunków) po normalizacji L2 wynosi dokładnie 1.0.
    #
    # Oczekiwane wartości na podstawie aktualnej definicji w VIBE_MAP:
    # 
    # Dla GuiltyUser (GUILTY_PLEASURE):
    # - Comedy: 2.5, Action: 1.3, Romance: 1.2
    # - L2 norm = sqrt(2.5^2 + 1.3^2 + 1.2^2) = sqrt(6.25 + 1.69 + 1.44) = sqrt(9.38) ≈ 3.0626785
    # - Normalized:
    #   Comedy: 2.5 / 3.0626785 ≈ 0.8163
    #   Action: 1.3 / 3.0626785 ≈ 0.4245
    #   Romance: 1.2 / 3.0626785 ≈ 0.3918
    #
    # Dla ThrillerUser (SPINE_CHILLING, MIND_BENDER, ADRENALINE, EXISTENTIAL):
    # - SPINE_CHILLING: Horror: 4.0, Mystery: 0.5, Thriller: 2.0
    # - MIND_BENDER: Science Fiction: 1.0, Mystery: 2.5, Thriller: 1.5
    # - ADRENALINE: Action: 2.5, Thriller: 1.7, Crime: 1.0
    # - EXISTENTIAL: Drama: 2.0, Mystery: 1.0, Thriller: 1.5
    #
    # Suma nieunormowana gatunków ThrillerUser:
    # - Horror: 4.0
    # - Mystery: 0.5 + 2.5 + 1.0 = 4.0
    # - Thriller: 2.0 + 1.5 + 1.7 + 1.5 = 6.7
    # - Science Fiction: 1.0
    # - Action: 2.5
    # - Crime: 1.0
    # - Drama: 2.0
    #
    # L2 norm = sqrt(4.0^2 + 4.0^2 + 6.7^2 + 1.0^2 + 2.5^2 + 1.0^2 + 2.0^2)
    #         = sqrt(16.0 + 16.0 + 44.89 + 1.0 + 6.25 + 1.0 + 4.0) = sqrt(89.14) ≈ 9.4413982
    # - Normalized:
    #   Horror: 4.0 / 9.4413982 ≈ 0.4237
    #   Mystery: 4.0 / 9.4413982 ≈ 0.4237
    #   Thriller: 6.7 / 9.4413982 ≈ 0.7096
    #   Science Fiction: 1.0 / 9.4413982 ≈ 0.1059
    #   Action: 2.5 / 9.4413982 ≈ 0.2648
    #   Crime: 1.0 / 9.4413982 ≈ 0.1059
    #   Drama: 2.0 / 9.4413982 ≈ 0.2118
    
    weights_dict = {}
    for prompt, weight in prompts_with_weights:
        # Wyciągamy nazwę gatunku z wygenerowanego promptu
        # Format promptu w _create_user_prompts: "A {self.meeting_type} movie in the {genre} genre, featuring..."
        genre = prompt.split("in the ")[1].split(" genre")[0]
        weights_dict[genre] = weight

    # Wyliczamy dokładne oczekiwane wartości
    norm_guilty = (2.5**2 + 1.3**2 + 1.2**2)**0.5
    norm_thriller = (4.0**2 + 4.0**2 + 6.7**2 + 1.0**2 + 2.5**2 + 1.0**2 + 2.0**2)**0.5

    expected_comedy = 2.5 / norm_guilty
    expected_romance = 1.2 / norm_guilty
    expected_horror = 4.0 / norm_thriller
    expected_thriller = 6.7 / norm_thriller
    expected_action = (1.3 / norm_guilty) + (2.5 / norm_thriller)
    expected_drama = 2.0 / norm_thriller

    assert pytest.approx(weights_dict["Comedy"], 0.0001) == expected_comedy
    assert pytest.approx(weights_dict["Romance"], 0.0001) == expected_romance
    assert pytest.approx(weights_dict["Horror"], 0.0001) == expected_horror
    assert pytest.approx(weights_dict["Thriller"], 0.0001) == expected_thriller
    assert pytest.approx(weights_dict["Action"], 0.0001) == expected_action
    assert pytest.approx(weights_dict["Drama"], 0.0001) == expected_drama
