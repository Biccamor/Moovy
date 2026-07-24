"""
Zestaw 20 scenariuszy testowych dla systemu rekomendacji.

Każdy scenariusz zawiera:
- Opis sytuacji (komentarz)
- meeting_type: SOLO / RANDKA / EKIPA / RODZINA
- Lista userów z ich preferencjami (vibes, hard_nos, max_runtime, eras)

Scenariusze pokrywają:
- 1-osobowe (SOLO)
- 2-osobowe (RANDKA, ale też EKIPA)
- 3-5 osobowe (EKIPA, RODZINA)
- Podobne vibes (harmonia)
- Różne/konfliktowe vibes (potencjalny conflict detection)
- Skrajne parametry (runtime, eras)

Użycie:
    from test.test_datasets import SCENARIOS
    for s in SCENARIOS:
        print(s["name"], s["meeting_type"], len(s["users"]))
"""

from uuid import uuid4

# ── Helper do tworzenia usera ───────────────────────────────────────

def _user(name: str, vibes: list, hard_nos: list = None, max_runtime: int = 120,
          allow_seen: bool = False, eras: list = None):
    """Tworzy dict usera gotowy do użycia w MovieSession."""
    return {
        "user_id": str(uuid4()),
        "user_name": name,
        "personal_vibe": {
            "vibes": vibes,
            "hard_nos": hard_nos or [],
            "max_runtime": max_runtime,
            "allow_seen": allow_seen,
            "eras": eras or [],
        }
    }


# ═══════════════════════════════════════════════════════════════════
#  SCENARIUSZE
# ═══════════════════════════════════════════════════════════════════

SCENARIOS = [

    # ──────────────────────────────────────────────────────────────
    #  SOLO (1 osoba)
    # ──────────────────────────────────────────────────────────────

    {
        # 1. Klasyczny solo chill — jedna vibe, domyślne ustawienia
        "name": "solo_pizza_chill",
        "description": "Jedna osoba, wieczór z pizzą, nic wymagającego",
        "meeting_type": "SOLO",
        "users": [
            _user("Tomek", vibes=["LAUGH_RIOT"]),
        ],
    },
    {
        # 2. Solo ambitne kino — ktoś chce się "zamyślić"
        "name": "solo_ambitious_cinephile",
        "description": "Samotny kinofile szukający czegoś wymagającego",
        "meeting_type": "SOLO",
        "users": [
            _user("Marta", vibes=["EXISTENTIAL", "MIND_BENDER"], max_runtime=180, eras=["2010s", "2020s"]),
        ],
    },
    {
        # 3. Solo horror night
        "name": "solo_horror_night",
        "description": "Samotna sesja horrorowa — krótki film",
        "meeting_type": "SOLO",
        "users": [
            _user("Kasia", vibes=["SPINE_CHILLING"], hard_nos=["LAUGH_RIOT"], max_runtime=100),
        ],
    },
    {
        # 4. Solo family fun — animacje, Pixar, Disney
        "name": "solo_family_fun",
        "description": "Wieczór z animacjami — Pixar, Disney, coś wholesome",
        "meeting_type": "SOLO",
        "users": [
            _user("Piotr", vibes=["FAMILY_FUN", "EPIC_JOURNEY"], max_runtime=150),
        ],
    },
    {
        # 5. Solo — brak preferencji (edge case)
        "name": "solo_no_preferences",
        "description": "User nie podał żadnych vibes — system powinien dać coś domyślnego",
        "meeting_type": "SOLO",
        "users": [
            _user("Ghost", vibes=[]),
        ],
    },

    # ──────────────────────────────────────────────────────────────
    #  RANDKA (2 osoby, romantycznie)
    # ──────────────────────────────────────────────────────────────

    {
        # 6. Klasyczna randka — oboje chcą romantycznie
        "name": "date_both_romantic",
        "description": "Oboje chcą romantycznego wieczoru — harmonia",
        "meeting_type": "RANDKA",
        "users": [
            _user("Anna", vibes=["DATE_NIGHT", "DEEP_FEELS"]),
            _user("Michał", vibes=["DATE_NIGHT", "LAUGH_RIOT"]),
        ],
    },
    {
        # 7. Randka — jeden romantyk, drugi chce akcję (konflikt)
        "name": "date_romance_vs_action",
        "description": "Ona chce romcom, on chce adrenaliny — KONFLIKT",
        "meeting_type": "RANDKA",
        "users": [
            _user("Ola", vibes=["DATE_NIGHT", "DEEP_FEELS"], hard_nos=["ADRENALINE"]),
            _user("Bartek", vibes=["ADRENALINE", "MIND_BENDER"], hard_nos=["DATE_NIGHT"]),
        ],
    },
    {
        # 8. Randka — oboje guilty pleasure
        "name": "date_guilty_pleasure_harmony",
        "description": "Oboje lubią 'cringe' kino — idealna para",
        "meeting_type": "RANDKA",
        "users": [
            _user("Zuzia", vibes=["GUILTY_PLEASURE", "LAUGH_RIOT"]),
            _user("Dawid", vibes=["GUILTY_PLEASURE", "LAUGH_RIOT"]),
        ],
    },
    {
        # 9. Randka — horror + romans (dziwna mieszanka)
        "name": "date_horror_romance_mix",
        "description": "On chce horroru, ona romansu — system musi znaleźć kompromis",
        "meeting_type": "RANDKA",
        "users": [
            _user("Igor", vibes=["SPINE_CHILLING"], max_runtime=100),
            _user("Lena", vibes=["DATE_NIGHT", "DEEP_FEELS"], max_runtime=140),
        ],
    },

    # ──────────────────────────────────────────────────────────────
    #  EKIPA (2-5 osób, luźno)
    # ──────────────────────────────────────────────────────────────

    {
        # 9.1. Ekipa 5 osób — super horror
        "name": "crew_5_horror_romance_extremal_conflict",
        "description": "5 osób — 2 horror fanów, 2 romantyków, 1 thriller fan — skrajny konflikt",
        "meeting_type": "EKIPA",
        "users": [
            _user("Horror 1", vibes=["SPINE_CHILLING", "EXISTENTIAL"], max_runtime=130),
            _user("Horror 2", vibes=["SPINE_CHILLING"], max_runtime=120),
            _user("Horror 3", vibes=["SPINE_CHILLING", "MIND_BENDER"], max_runtime=140),
            _user("Horror 4", vibes=["SPINE_CHILLING", "GUILTY_PLEASURE"], max_runtime=130),
            _user("Thriller", vibes=["ADRENALINE", "MIND_BENDER", "EXISTENTIAL"], max_runtime=135),
        ],
    },

    {
        # 10. Ekipa 2 osoby — identyczne viby
        "name": "crew_2_identical_vibes",
        "description": "Dwóch kumpli — obaj chcą tego samego",
        "meeting_type": "EKIPA",
        "users": [
            _user("Kamil", vibes=["ADRENALINE", "LAUGH_RIOT"]),
            _user("Łukasz", vibes=["ADRENALINE", "LAUGH_RIOT"]),
        ],
    },
    {
        # 11. Ekipa 3 osoby — każdy inny gatunek (potencjalny konflikt)
        "name": "crew_3_diverse_conflict",
        "description": "Trzy totalnie różne osoby — horror, romcom, sci-fi",
        "meeting_type": "EKIPA",
        "users": [
            _user("Adam", vibes=["SPINE_CHILLING"]),
            _user("Ewa", vibes=["DATE_NIGHT"]),
            _user("Marek", vibes=["MIND_BENDER", "EPIC_JOURNEY"]),
        ],
    },
    {
        # 12. Ekipa 4 osoby — wszyscy pizza chill (brak konfliktu)
        "name": "crew_4_all_chill",
        "description": "Czterech ziomków, pizza, piwo, coś lekkiego",
        "meeting_type": "EKIPA",
        "users": [
            _user("Szymon", vibes=["PIZZA_CHILL"]),
            _user("Filip", vibes=["PIZZA_CHILL", "LAUGH_RIOT"]),
            _user("Kuba", vibes=["LAUGH_RIOT"]),
            _user("Daniel", vibes=["PIZZA_CHILL", "GUILTY_PLEASURE"]),
        ],
    },
    {
        # 13. Ekipa 5 osób — mieszanka ale z dominantą akcji
        "name": "crew_5_action_dominant",
        "description": "5 osób, większość chce akcję, jeden outlier",
        "meeting_type": "EKIPA",
        "users": [
            _user("Wojtek", vibes=["ADRENALINE"]),
            _user("Paweł", vibes=["ADRENALINE", "EPIC_JOURNEY"]),
            _user("Tomasz", vibes=["ADRENALINE", "MIND_BENDER"]),
            _user("Jakub", vibes=["ADRENALINE"]),
            _user("Robert", vibes=["DEEP_FEELS", "INSPIRING"]),  # outlier
        ],
    },
    {
        # 14. Ekipa 3 osoby — runtime conflict (30min vs 240min)
        "name": "crew_3_runtime_extremes",
        "description": "Jeden chce krótki film, drugi długi — test kalkulacji runtime",
        "meeting_type": "EKIPA",
        "users": [
            _user("Ania", vibes=["PIZZA_CHILL"], max_runtime=30),
            _user("Basia", vibes=["PIZZA_CHILL"], max_runtime=240),
            _user("Celina", vibes=["PIZZA_CHILL"], max_runtime=120),
        ],
    },
    {
        # 15. Ekipa 3 osoby — jeden bez preferencji, dwóch z silnymi vibes
        "name": "crew_3_one_empty_prefs",
        "description": "Jeden user nie podał vibes — system musi sobie poradzić",
        "meeting_type": "EKIPA",
        "users": [
            _user("Jan", vibes=[]),
            _user("Piotr", vibes=["AMBITIOUS", "INSPIRING"]),
            _user("Karol", vibes=["MIND_BENDER", "ADRENALINE"]),
        ],
    },

    # ──────────────────────────────────────────────────────────────
    #  RODZINA
    # ──────────────────────────────────────────────────────────────

    {
        # 16. Rodzina 3 osoby — rodzice + dziecko, bezpiecznie
        "name": "family_safe_choice",
        "description": "Mama, tata, dziecko — nic strasznego, nic ambitnego",
        "meeting_type": "RODZINA",
        "users": [
            _user("Mama", vibes=["PIZZA_CHILL", "FAMILY_FUN"], hard_nos=["SPINE_CHILLING"]),
            _user("Tata", vibes=["EPIC_JOURNEY", "PIZZA_CHILL"], hard_nos=["SPINE_CHILLING"]),
            _user("Dziecko", vibes=["FAMILY_FUN", "LAUGH_RIOT"], hard_nos=["SPINE_CHILLING", "DEEP_FEELS"]),
        ],
    },
    {
        # 17. Rodzina 4 osoby — nastolatki chcą horroru, rodzice nie
        "name": "family_teen_vs_parents",
        "description": "Konflikt pokoleniowy — młodzi chcą horroru, starsi komedii",
        "meeting_type": "RODZINA",
        "users": [
            _user("Mama", vibes=["LAUGH_RIOT", "DATE_NIGHT"], hard_nos=["SPINE_CHILLING"]),
            _user("Tata", vibes=["ADRENALINE", "PIZZA_CHILL"], hard_nos=["SPINE_CHILLING"]),
            _user("Syn", vibes=["SPINE_CHILLING", "ADRENALINE"]),
            _user("Córka", vibes=["SPINE_CHILLING", "MIND_BENDER"]),
        ],
    },
    {
        # 18. Rodzina 5 osób — wszyscy chcą family fun (harmonia)
        "name": "family_fun_harmony",
        "description": "Cała rodzina — coś dla każdego, animacje i komedie familijne",
        "meeting_type": "RODZINA",
        "users": [
            _user("Babcia", vibes=["FAMILY_FUN", "INSPIRING"], max_runtime=100),
            _user("Dziadek", vibes=["FAMILY_FUN", "EPIC_JOURNEY"], max_runtime=120),
            _user("Mama", vibes=["FAMILY_FUN"]),
            _user("Tata", vibes=["FAMILY_FUN", "PIZZA_CHILL"]),
            _user("Wnuk", vibes=["FAMILY_FUN", "LAUGH_RIOT"]),
        ],
    },

    # ──────────────────────────────────────────────────────────────
    #  EDGE CASES / SPECJALNE
    # ──────────────────────────────────────────────────────────────

    {
        # 19. Maksymalnie konfliktowy — każdy vibe inny + hard_nos blokują się nawzajem
        "name": "maximum_conflict",
        "description": "3 osoby, każdy chce czegoś innego i blokuje to co inni lubią",
        "meeting_type": "EKIPA",
        "users": [
            _user("X", vibes=["SPINE_CHILLING", "EXISTENTIAL"],
                  hard_nos=["LAUGH_RIOT"]),
            _user("Y", vibes=["LAUGH_RIOT"],
                  hard_nos=["SPINE_CHILLING", "EXISTENTIAL"]),
            _user("Z", vibes=["DEEP_FEELS", "HISTORY_LESSON"],
                  hard_nos=["ADRENALINE", "SPINE_CHILLING"]),
        ],
    },
    {
        # 20. "All vibes" — user który chce WSZYSTKO (edge case)
        "name": "solo_all_vibes",
        "description": "User zaznaczył wszystkie viby — system musi wybrać coś wszechstronnego",
        "meeting_type": "SOLO",
        "users": [
            _user("MaxVibes", vibes=[
                "EXISTENTIAL", "MIND_BENDER", "ADRENALINE", "DATE_NIGHT",
                "DEEP_FEELS", "LAUGH_RIOT", "SPINE_CHILLING", "FAMILY_FUN",
                "HISTORY_LESSON", "EPIC_JOURNEY", "GUILTY_PLEASURE",
            ], max_runtime=240, allow_seen=True),
        ],
    },
    {
        # 21. Normalizacja test - 2 osoby: jedna guilty pleasure, druga 4 vibes thriller/horror
        "name": "normalization_guilty_vs_thriller",
        "description": "2 osoby: jedna chce tylko GUILTY_PLEASURE, druga 4 vibes thriller/horror (SPINE_CHILLING, MIND_BENDER, ADRENALINE, EXISTENTIAL). Testuje czy normalizacja wektora zapobiega dominacji preferencji drugiej osoby.",
        "meeting_type": "RANDKA",
        "users": [
            _user("GuiltyUser", vibes=["GUILTY_PLEASURE"]),
            _user("ThrillerUser", vibes=["SPINE_CHILLING", "MIND_BENDER", "ADRENALINE", "EXISTENTIAL"]),
        ],
    },
]


# ── Statystyki datasetu (do debugowania) ────────────────────────────

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  DATASET: {len(SCENARIOS)} scenariuszy testowych")
    print(f"{'='*60}\n")

    from collections import Counter
    type_counts = Counter(s["meeting_type"] for s in SCENARIOS)
    size_counts = Counter(len(s["users"]) for s in SCENARIOS)

    print("  Meeting types:")
    for mt, count in type_counts.most_common():
        print(f"    {mt}: {count}")

    print(f"\n  Rozmiary grup:")
    for size, count in sorted(size_counts.items()):
        print(f"    {size} osób: {count} scenariuszy")

    print(f"\n{'-'*60}")
    for i, s in enumerate(SCENARIOS, 1):
        users_str = ", ".join(u["user_name"] for u in s["users"])
        vibes_all = set()
        for u in s["users"]:
            vibes_all.update(u["personal_vibe"]["vibes"])
        print(f"  {i:2d}. [{s['meeting_type']:7s}] {s['name']}")
        print(f"      Userzy: {users_str}")
        print(f"      Vibes:  {', '.join(sorted(vibes_all)) or '(brak)'}")
        print()
