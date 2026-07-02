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
            vibes=["SPINE_CHILLING", "MIND_BENDER", "ADRENALINE", "AMBITIOUS"],
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
    # Oczekiwane wartości na podstawie definicji w VIBE_MAP:
    # 
    # Dla GuiltyUser (GUILTY_PLEASURE):
    # - Comedy: 1.5, Action: 1.3, Romance: 1.2
    # - L2 norm = sqrt(1.5^2 + 1.3^2 + 1.2^2) = sqrt(2.25 + 1.69 + 1.44) = sqrt(5.38) ≈ 2.3194827
    # - Normalized:
    #   Comedy: 1.5 / 2.3194827 ≈ 0.6467
    #   Action: 1.3 / 2.3194827 ≈ 0.5605
    #   Romance: 1.2 / 2.3194827 ≈ 0.5174
    #
    # Dla ThrillerUser (SPINE_CHILLING, MIND_BENDER, ADRENALINE, AMBITIOUS):
    # - SPINE_CHILLING: Horror: 3.5, Mystery: 1.0, Thriller: 1.5
    # - MIND_BENDER: Science Fiction: 1.0, Mystery: 1.5, Thriller: 1.5
    # - ADRENALINE: Action: 2.0, Thriller: 1.4, Crime: 1.0
    # - AMBITIOUS: Drama: 2.0, Mystery: 1.0, Thriller: 1.5
    #
    # Suma nieunormowana gatunków ThrillerUser:
    # - Horror: 3.5
    # - Mystery: 1.0 + 1.5 + 1.0 = 3.5
    # - Thriller: 1.5 + 1.5 + 1.4 + 1.5 = 5.9
    # - Science Fiction (czyli "Science Fiction"): 1.0
    # - Action: 2.0
    # - Crime: 1.0
    # - Drama: 2.0
    #
    # L2 norm = sqrt(3.5^2 + 3.5^2 + 5.9^2 + 1.0^2 + 2.0^2 + 1.0^2 + 2.0^2)
    #         = sqrt(12.25 + 12.25 + 34.81 + 1.0 + 4.0 + 1.0 + 4.0) = sqrt(69.31) ≈ 8.3252627
    # - Normalized:
    #   Horror: 3.5 / 8.3252627 ≈ 0.4204
    #   Mystery: 3.5 / 8.3252627 ≈ 0.4204
    #   Thriller: 5.9 / 8.3252627 ≈ 0.7087
    #   Science Fiction: 1.0 / 8.3252627 ≈ 0.1201
    #   Action: 2.0 / 8.3252627 ≈ 0.2402
    #   Crime: 1.0 / 8.3252627 ≈ 0.1201
    #   Drama: 2.0 / 8.3252627 ≈ 0.2402
    
    weights_dict = {}
    for prompt, weight in prompts_with_weights:
        # Wyciągamy nazwę gatunku z wygenerowanego promptu
        # Format promptu w _create_user_prompts: "A {self.meeting_type} movie in the {genre} genre, featuring..."
        genre = prompt.split("in the ")[1].split(" genre")[0]
        weights_dict[genre] = weight

    # Wyliczamy dokładne oczekiwane wartości
    norm_guilty = (1.5**2 + 1.3**2 + 1.2**2)**0.5
    norm_thriller = (3.5**2 + 3.5**2 + 5.9**2 + 1.0**2 + 2.0**2 + 1.0**2 + 2.0**2)**0.5

    expected_comedy = 1.5 / norm_guilty
    expected_romance = 1.2 / norm_guilty
    expected_horror = 3.5 / norm_thriller
    expected_thriller = 5.9 / norm_thriller
    expected_action = (1.3 / norm_guilty) + (2.0 / norm_thriller)
    expected_drama = 2.0 / norm_thriller

    assert pytest.approx(weights_dict["Comedy"], 0.0001) == expected_comedy
    assert pytest.approx(weights_dict["Romance"], 0.0001) == expected_romance
    assert pytest.approx(weights_dict["Horror"], 0.0001) == expected_horror
    assert pytest.approx(weights_dict["Thriller"], 0.0001) == expected_thriller
    assert pytest.approx(weights_dict["Action"], 0.0001) == expected_action
    assert pytest.approx(weights_dict["Drama"], 0.0001) == expected_drama
