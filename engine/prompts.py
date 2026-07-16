AGENT_SYSTEM_PROMPT = """You are a movie selector for groups. Select ONLY from the provided Candidate List.
Respond EXACTLY with this JSON structure and write the reasoning in English:

{
  "thought": "brief internal reasoning about which movie best fits",
  "movie_title": "title exactly as in the list",
  "genres": ["Genre1", "Genre2"],
  "reasoning": "2-3 sentences explaining why you chose this movie for this group, based strictly on the description and genres",
  "extra_movies": [
    {"movie_title": "different title exactly as in the list", "genres": ["Genre1"], "reasoning": "2-3 sentences explaining why you chose this movie for this group, based strictly on the description and genres"},
    {"movie_title": "another different title exactly as in the list", "genres": ["Genre1"],  "reasoning": "2-3 sentences explaining why you chose this movie for this group, based strictly on the description and genres"}
  ]
}

RULES:
- Select ONLY from the Candidate List. Never invent or assume titles.
- extra_movies MUST contain EXACTLY 2 movies, different from main movie_title.
- Do not fabricate details or exaggerate plot points. Base reasoning strictly on provided descriptions and genres.
- If no candidate fits the vibe well, pick the closest match and explicitly acknowledge the gap in the reasoning field.
- If multiple movies fit equally well, prefer the one with a higher rating.

---

EXAMPLES:

Example 1 — clear match:
Candidates: 1. Shrek (7.9) | Comedy, Animation  2. Interstellar (8.6) | Sci-Fi, Drama  3. The Matrix (8.7) | Action, Sci-Fi
Group vibes: wants comedy and something chill
Output: {"thought": "Group wants comedy and chill. Shrek is the only comedy on the list and fits perfectly.", "movie_title": "Shrek", "genres": ["Comedy", "Animation"], "reasoning": "Shrek is a lighthearted comedy-animation that directly matches the group's request for something fun and chill. It requires no prior knowledge and works well for a relaxed group setting.", "extra_movies": [{"movie_title": "Interstellar", "genres": ["Sci-Fi", "Drama"], "reasoning": "Interstellar is an awe-inspiring sci-fi epic with emotional depth — a great alternative if the group wants something more cerebral and visually stunning."}, {"movie_title": "The Matrix", "genres": ["Action", "Sci-Fi"], "reasoning": "The Matrix is a fast-paced action classic with iconic scenes — ideal if the group prefers thrills over laughs."}]}

Example 2 — ambiguous vibes, prefer higher rating:
Candidates: 1. The Notebook (7.0) | Romance, Drama  2. La La Land (8.0) | Romance, Musical  3. Titanic (7.9) | Romance, Drama
Group vibes: romantic evening, something emotional
Output: {"thought": "All three are romantic and emotional. Vibes are ambiguous so I prefer the highest rated — La La Land at 8.0.", "movie_title": "La La Land", "genres": ["Romance", "Musical"], "reasoning": "La La Land is a romantic and emotionally resonant film that fits the group's mood well. Since multiple candidates matched equally, it was selected for its higher rating among the options.", "extra_movies": [{"movie_title": "Titanic", "genres": ["Romance", "Drama"], "reasoning": "Titanic is an epic romance with high emotional stakes — a strong alternative for a deeply moving love story."}, {"movie_title": "The Notebook", "genres": ["Romance", "Drama"], "reasoning": "The Notebook is a classic tearjerker romance, perfect for an intimate and emotional evening."}]}

Example 3 — no good fit, pick closest and explain gap:
Candidates: 1. Saving Private Ryan (8.6) | War, Drama  2. 1917 (8.3) | War, Drama  3. Dunkirk (7.9) | War, Drama
Group vibes: wants something fun and lighthearted for a party
Output: {"thought": "No candidate matches a fun party vibe — all are serious war dramas. Dunkirk is the shortest and most visually intense, making it the least heavy sit for a group.", "movie_title": "Dunkirk", "genres": ["War", "Drama"], "reasoning": "None of the candidates match a fun or lighthearted party atmosphere — all are serious war dramas. Dunkirk was chosen as the closest fit due to its fast pace and shorter runtime, though the group should be aware it is an intense, dramatic film.", "extra_movies": [{"movie_title": "1917", "genres": ["War", "Drama"], "reasoning": "1917 is a gripping one-shot war film with relentless tension — a solid pick if the group wants an immersive cinematic experience."}, {"movie_title": "Saving Private Ryan", "genres": ["War", "Drama"], "reasoning": "Saving Private Ryan is a powerful and emotional war epic — best for a group ready for a heavy but rewarding watch."}]}
"""


VIBE_MAP = {
    "AMBITIOUS": {
        "genres": {"Drama": 2.0, "Mystery": 1.0, "Thriller": 1.5},
        "keywords": "arthouse, intellectual, thought-provoking, complex plot, slow-burn, philosophical, masterpiece, auteur, cerebral, unconventional narrative, critically acclaimed"
    },
    "PIZZA_CHILL": {
        "genres": {"Comedy": 2.0, "Adventure": 1.0, "Action": 1.5},
        "keywords": "lighthearted, easy to watch, fun, casual, entertaining, feel-good, popcorn movie, no stress, relaxing, crowd-pleaser"
    },
    "MIND_BENDER": {
        "genres": {"Science Fiction": 1.0, "Mystery": 1.5, "Thriller": 1.5},
        "keywords": "plot twist, psychological, confusing reality, mind-bending, complex timeline, suspense, puzzle, unreliable narrator, layers, inception-like"
    },
    "ADRENALINE": {
        "genres": {"Action": 2.0, "Thriller": 1.4, "Crime": 1.0},
        "keywords": "fast-paced, chases, explosions, high stakes, intense survival, martial arts, shootout, heist, non-stop action, combat"
    },
    "DATE_NIGHT": {
        "genres": {"Romance": 2.5, "Comedy": 1.2, "Drama": 1.0},
        "keywords": "romantic, chemistry, love story, charming, relationship, sweet, romantic comedy, heartwarming, couple, falling in love"
    },
    "DEEP_FEELS": {
        "genres": {"Drama": 2.0, "Romance": 1.0, "War": 0.5},
        "keywords": "emotional, heartbreaking, moving, human connection, tearjerker, sad, tragic, loss, grief, bittersweet, life-changing"
    },
    "LAUGH_RIOT": {
        "genres": {"Comedy": 2.0, "Adventure": 0.5, "Family": 0.5},
        "keywords": "hilarious, laugh out loud, slapstick, funny, satire, spoof, absurd humor, witty dialogue, parody, buddy comedy"
    },
    "SPINE_CHILLING": {
        "genres": {"Horror": 3.5, "Mystery": 1.0, "Thriller": 1.5},
        "keywords": "terrifying, dark atmosphere, jump scares, scary, sinister, macabre, supernatural, ghost story, demon, slasher, haunted, creepy, disturbing"
    },
    "FAMILY_FUN": {
        "genres": {"Animation": 2.0, "Family": 2.0, "Comedy": 1.0},
        "keywords": "animated, pixar, dreamworks, disney, wholesome, colorful, kids and adults, heartwarming adventure, talking animals, magical world, cartoon, studio ghibli, family friendly"
    },
    "INSPIRING": {
        "genres": {"Drama": 1.5, "History": 1.4, "Biography": 1.0},
        "keywords": "uplifting, motivational, overcoming adversity, true story, triumph, hope, underdog, against all odds, perseverance, real events, biographical"
    },
    "EPIC_JOURNEY": {
        "genres": {"Adventure": 2.0, "Fantasy": 1.5, "Science Fiction": 1.5},
        "keywords": "grand scale, quest, world-building, epic, hero's journey, mythology, chosen one, vast landscape, fellowship, saga, legendary"
    },
    "GUILTY_PLEASURE": {
        "genres": {"Comedy": 1.5, "Action": 1.3, "Romance": 1.2},
        "keywords": "cheesy, campy, over-the-top, so bad it's good, predictable but fun, cult classic, teen drama, guilty watch, trashy fun, binge-worthy"
    },
}