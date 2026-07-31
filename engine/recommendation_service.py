from schemas.schemas import MovieSession
from database.database_setup import Room_Session, User
from uuid import uuid4, UUID
import numpy as np
from engine.vector import create_vector, hybrid_search
from engine.llm_decider import decide
from engine.prompts import VIBE_MAP
from sqlmodel import select

class RecomService:

    def __init__(self, meta_data: MovieSession, session):
        self.session = session
        self.meta_data = meta_data
        self.meeting_type = self.meta_data.meeting_type
        self.user_list = self.meta_data.users
        self.preferences = self.meta_data.final_preferences

    async def _add_db(self) -> UUID:
        """
        Zapisuje sesję do bazy danych i zwraca session_id.
        Nie wywołuje AI – jest szybki.
        """
        users_seen = {
            str(u.user_id): {
                "allow_seen": u.personal_vibe.allow_seen,
                "user_name": u.user_name
            } for u in self.user_list
        }
        recommended_time, min_time = self._get_time()
        user_id_list = [str(u.user_id) for u in self.user_list]
        preferences_excluded = [
            u.model_dump(exclude={"preferences": {"time", "allow_seen"}}, mode='json')
            for u in self.user_list
        ]

        agent_prompt = self._create_user_prompts()
        
        # Jeśli użytkownicy nie podali żadnych preferencji (lub są puste), używamy domyślnego promptu
        if not agent_prompt:
            agent_prompt = [(f"A {self.meeting_type} movie.", 1.0)]
            
        prompts = [p for p, _ in agent_prompt]
        weights = [w for _, w in agent_prompt]
        vectors = await create_vector(prompts)

        group_vector = self._build_group_vector(vectors, weights)
        conflict = self._detect_conflict(vectors)

        session_id = uuid4()
        new_group = Room_Session(
            session_id=session_id,
            recomended_runtime=recommended_time,
            min_runtime=min_time,
            occasion=self.meeting_type,
            allow_seen=users_seen,
            preferences=preferences_excluded,
            users_in_session=user_id_list,
            embedding_preferences=group_vector,
            conflict=conflict
        )

        self.session.add(new_group)
        self.session.commit()

        return session_id

    def _create_user_prompts(self) -> list[tuple[str, float]]:
        genre_data = {}
        for user in self.user_list: 
            user_genres = {}
            user_kw = {}
            for vibe in user.personal_vibe.vibes:
                vibe_info = VIBE_MAP.get(vibe)
                if not vibe_info: continue
                kw_list = [k.strip() for k in vibe_info["keywords"].split(",")]
                for genre, weight in vibe_info["genres"].items():
                    user_genres[genre] = user_genres.get(genre, 0.0) + weight
                    user_kw.setdefault(genre, set()).update(kw_list)

         # normalizuj wektor usera do długości 1 żeby każdy user miał równy głos
            norm = np.sqrt(sum(v ** 2 for v in user_genres.values())) if user_genres else 0
            if norm == 0: continue

            for genre, weight in user_genres.items():
                if genre not in genre_data:
                    genre_data[genre] = {"count": 0, "keywords": set()}
                genre_data[genre]["count"] += weight / norm
                genre_data[genre]["keywords"].update(user_kw.get(genre, set()))

        result = []
        for genre, data in genre_data.items():
            keywords_str = ", ".join(sorted(data["keywords"]))
            prompt = f"A {self.meeting_type} movie in the {genre} genre, featuring: {keywords_str}. It has a plot focusing on these elements."
            result.append((prompt, float(data["count"])))

        return result
    
    def _create_prompt(self, conflict: bool) -> str:
        prompt = ""
        for user in self.user_list:
            vibes = user.personal_vibe.vibes
            if not vibes:
                prompt += f"user: {user.user_name} wants all kinds of movies\n"
                continue
            
            user_genres = {}
            user_keywords = set()
            for v in vibes:
                v_info = VIBE_MAP.get(v)
                if v_info:
                    for g, w in v_info["genres"].items():
                        user_genres[g] = user_genres.get(g, 0) + w
                    user_keywords.update([k.strip() for k in v_info["keywords"].split(",")])
            
            genres_list = [f"{g} (x{count})" if count > 1 else g for g, count in user_genres.items()]
            genres_str = ", ".join(sorted(genres_list))
            keywords_str = ", ".join(sorted(user_keywords))
            prompt += f"user: {user.user_name} wants {genres_str} movies with elements like: {keywords_str}\n"
            
        prompt += f"meeting type: {self.meeting_type}\n"
        if conflict:
            prompt += "NOTE: users have very different tastes. Pick a film nobody will regret, not one person will love."
        return prompt
 
    def _build_group_vector(self, vectors: list, weights:list):
        w = np.array(weights, dtype=float)
        w /= w.sum() # zamieniamy kazdą ilość na procent tego jak pozadany jest dany gatunek
        w = w[:, None] # zmienamy rozmiar na (1,1024)
        v = np.array(vectors)
        group_vector = (v*w).sum(axis=0) 
        group_vector /= np.linalg.norm(group_vector) # normalizacja dlugosci
        return group_vector.tolist()
    
    def _detect_conflict(self, vectors: list) -> bool:
        if len(vectors) < 2:
            return False
        v = np.array(vectors)
        v = v / np.linalg.norm(v, axis=1, keepdims=True)
        sim_matrix = v @ v.T
        np.fill_diagonal(sim_matrix, 1.0)
        
        avg_sim = (sim_matrix.sum() - len(vectors)) / (len(vectors) * (len(vectors) - 1)) # claude ugotowal z tym wzorem
        return avg_sim < 0.65
    
    def _get_time(self) -> tuple[int, int]:
        """
        Zwraca (recommended_time, min_time) na podstawie preferencji użytkowników.
        """
        times = [u.personal_vibe.max_runtime for u in self.user_list]
        if not times:
            return (120, 90)
        min_time = min(times)
        mean_time = np.mean(times)
        recommended_time = int(np.floor((float(min_time) + mean_time) / 2))
        return (recommended_time, min_time)

    @staticmethod
    async def get_recommendations_from_db(db_session: Room_Session, session):
        """
        Pobiera rekomendacje filmów na podstawie danych już zapisanej sesji w bazie.
        Wywołuje model AI – może być wolny.
        """
        vector = db_session.embedding_preferences
        max_runtime = max(db_session.recomended_runtime or 120, db_session.min_runtime or 90)

        group_genres = {}
        group_keywords = set()
        all_hard_nos = set()
        no_anime = False
        no_animation = False

        users_info = ""
        for u in (db_session.preferences or []):
            personal_vibe = u.get("personal_vibe", {})
            user_hard_nos = personal_vibe.get("hard_nos", [])
            all_hard_nos.update(user_hard_nos)
            if personal_vibe.get("no_anime"):
                no_anime = True
            if personal_vibe.get("no_animation"):
                no_animation = True

            vibes = personal_vibe.get("vibes", [])
            if not vibes:
                users_info += f"user: {u.get('user_name', 'unknown')} wants all kinds of movies\n"
                continue
            
            user_genres = {}
            user_keywords = set()
            for v in vibes:
                v_info = VIBE_MAP.get(v)
                if v_info:
                    for g, w in v_info["genres"].items():
                        user_genres[g] = user_genres.get(g, 0) + w
                        group_genres[g] = group_genres.get(g, 0) + w
                    kw_list = [k.strip() for k in v_info["keywords"].split(",")]
                    user_keywords.update(kw_list)
                    group_keywords.update(kw_list)
            
            genres_list = [f"{g} (x{count})" if count > 1 else g for g, count in user_genres.items()]
            genres_str = ", ".join(sorted(genres_list))
            keywords_str = ", ".join(sorted(user_keywords))
            users_info += f"user: {u.get('user_name', 'unknown')} wants {genres_str} movies with elements like: {keywords_str}\n"
            
        users_info += f"meeting type: {db_session.occasion}\n"
        if getattr(db_session, 'conflict', False):
            users_info += "NOTE: users have very different tastes. Pick a film nobody will regret, not one person will love."

        all_genres = [g for g, _ in sorted(group_genres.items(), key=lambda x: x[1], reverse=True)]
        reranker_query = f"A {db_session.occasion} movie featuring genres: {', '.join(all_genres)}. Elements and vibes: {', '.join(group_keywords)}."

        user_ids = [UUID(uid) for uid in (db_session.users_in_session or [])]
        user_list = session.exec(select(User).where(User.user_id.in_(user_ids))).all() if user_ids else []

        recommendations = await decide(session, vector, max_runtime, users_info, reranker_query, user_list=user_list, allow_seen_dict=db_session.allow_seen, hard_nos=list(all_hard_nos), limit_movies=100, no_anime=no_anime, no_animation=no_animation)
        return recommendations