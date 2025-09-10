import random
from dataclasses import dataclass
from typing import List, Dict, Tuple
from db import connect, get_candidates

# This class contains the filters and constraints the user can set when asking for a movie recommendation.
@dataclass
class Prefs:
    genres: List[str]                 # preferred genres (any match is acceptable)
    year_range: Tuple[int, int]       # (min_year, max_year)
    runtime_range: Tuple[int, int]    # (min_minutes, max_minutes)
    languages: List[str]              # e.g., ["en","ja"]; empty means any language
    min_rating: float                 # Minimum rating of movie (0-10)
    allowed_age_ratings: List[str]    # Allowed UK age ratings ["U","PG","12","12A","15","18"]

# Scoring function to score a movie based on how well it matches the user's preferences.
def score_row(row, prefs: Prefs) -> Dict[str, float]:
    rating_comp = (row["rating"] or 0) / 10.0

    # Year fit: closer to middle of range is better
    year_mid = (prefs.year_range[0] + prefs.year_range[1]) / 2
    year_span = max(1, prefs.year_range[1] - prefs.year_range[0])
    year_comp = 1.0 - min(1.0, abs((row["year"] or year_mid) - year_mid) / (year_span / 2))

    # Runtime fit: closer to middle of range is better
    run_mid = (prefs.runtime_range[0] + prefs.runtime_range[1]) / 2
    run_span = max(1, prefs.runtime_range[1] - prefs.runtime_range[0])
    runtime_comp = 1.0 - min(1.0, abs((row["runtime"] or run_mid) - run_mid) / (run_span / 2))

    # Genre bonus: if it matches any preferred genre, give a bonus
    genre_bonus = 0.15

    components = {
        "rating": rating_comp,
        "year_fit": year_comp,
        "runtime_fit": runtime_comp,
        "genre_bonus": genre_bonus,
    }
    total = rating_comp*0.5 + year_comp*0.2 + runtime_comp*0.15 + genre_bonus*0.15
    components["total"] = total
    return components

# ---- Weighted random selection based on scores.
def weighted_random_index(weights: List[float]) -> int:
    eps = 1e-6
    w = [max(eps, x) for x in weights]
    s = sum(w)
    r = random.random() * s
    cum = 0.0
    for i, x in enumerate(w):
        cum += x
        if r <= cum:
            return i
    return len(w) - 1

# Gets the genres for a movie.
def get_movie_genres(con, movie_id: int) -> List[str]:
    rows = con.execute(
        """SELECT g.name
           FROM genres g
           JOIN movie_genres mg ON g.id = mg.genre_id
           WHERE mg.movie_id = ?
           ORDER BY g.name""",
        (movie_id,)
    ).fetchall()
    return [r["name"] for r in rows]

# Main function to pick a movie from the database based on user preferences.
def pick_movie_from_db(prefs: Prefs, db_path: str = "movies.db"):
    con = connect(db_path)

    rows = get_candidates(
        con=con,
        genres_any=prefs.genres,
        year_range=prefs.year_range,
        runtime_range=prefs.runtime_range,
        languages=prefs.languages,
        min_rating=prefs.min_rating,
        allowed_age_ratings=prefs.allowed_age_ratings,
        exclude_ids=[] # previously used to exclude recent picks
    )
    if not rows:
        return {"error": "No movies match your filters. Try widening year/runtime, languages, or age ratings."}

    # Score each candidate movie
    scored = [score_row(r, prefs) for r in rows]

    # Select one based on weighted random
    weights = [s["total"] for s in scored]
    idx = weighted_random_index(weights)

    # Return the chosen movie with its score and components
    chosen = dict(rows[idx])
    chosen["genres"] = get_movie_genres(con, chosen["id"])
    return {
        "movie": chosen,
        "score": scored[idx]["total"],
        "components": {k: v for k, v in scored[idx].items() if k != "total"},
    }

# ---- TEST (command line) ----
if __name__ == "__main__":
    prefs = Prefs(
        genres=["Action","Science Fiction"],  
        year_range=(1990, 2024),
        runtime_range=(80, 160),
        languages=[],                        # any
        min_rating=7.5,
        allowed_age_ratings=["U","PG","12","12A","15","18"],
    )
    result = pick_movie_from_db(prefs)
    if "error" in result:
        print(result["error"])
    else:
        print("🎬 Your movie:", result["movie"]["title"])