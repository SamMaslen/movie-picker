# SQLite database access functions for movie picker app.

import sqlite3
from typing import Iterable, List, Dict, Any, Tuple
from datetime import datetime

# Connect to the SQLite database, enabling foreign keys and row factory.
def connect(db_path: str = "movies.db") -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con

# Insert or update a movie and its genres in the database.
def upsert_movie(con: sqlite3.Connection, movie: Dict[str, Any], genres: Iterable[Tuple[int, str]]):
    """
    movie: dict with keys:
      id,title,year,runtime,language,rating,age_rating,poster_path,overview,source_json
    genres: iterable of (genre_id, genre_name)
    """
    # Insert/update into movies (quote "year" to avoid parser quirks)
    con.execute("""
        INSERT INTO movies("id","title","year","runtime","language","rating","age_rating","poster_path","overview","source_json")
        VALUES (:id,:title,:year,:runtime,:language,:rating,:age_rating,:poster_path,:overview,:source_json)
        ON CONFLICT(id) DO UPDATE SET
          title=excluded.title,
          "year"=excluded."year",
          runtime=excluded.runtime,
          language=excluded.language,
          rating=excluded.rating,
          age_rating=excluded.age_rating,
          poster_path=excluded.poster_path,
          overview=excluded.overview,
          source_json=excluded.source_json
    """, movie)

    # Ensure genre exists, then link
    for gid, gname in genres:
        con.execute("INSERT OR IGNORE INTO genres(id,name) VALUES(?,?)", (gid, gname))
        con.execute("""
            INSERT OR IGNORE INTO movie_genres(movie_id, genre_id) VALUES(?,?)
        """, (movie["id"], gid))

    con.commit()

# History feature to track recently matched movies. Not currently used.
def record_pick(con: sqlite3.Connection, movie_id: int, user_id: int = 1):
    con.execute("INSERT INTO history(user_id, movie_id, picked_at) VALUES (?,?,?)",
                (user_id, movie_id, datetime.utcnow().isoformat()))
    con.commit()

def recent_history_ids(con: sqlite3.Connection, user_id: int = 1, limit: int = 20) -> List[int]:
    rows = con.execute("""
        SELECT movie_id FROM history
        WHERE user_id = ?
        ORDER BY picked_at DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    return [r["movie_id"] for r in rows]

def get_candidates(
        con: sqlite3.Connection,
        genres_any: List[str],
        year_range: Tuple[int, int],
        runtime_range: Tuple[int, int],
        languages: List[str],
        min_rating: float,
        allowed_age_ratings: List[str],
        exclude_ids: List[int]
) -> List[sqlite3.Row]:
    # Return movies matching the given filters.
    params = {
        "ymin": year_range[0], "ymax": year_range[1],
        "rmin": runtime_range[0], "rmax": runtime_range[1],
        "min_rating": min_rating
    }

    where = [
        "year BETWEEN :ymin AND :ymax",
        "runtime BETWEEN :rmin AND :rmax",
        "rating >= :min_rating"
    ]

    if languages:
        q_marks = ",".join("?" for _ in languages)
        where.append(f"language IN ({q_marks})")

    if allowed_age_ratings:
        q_marks2 = ",".join("?" for _ in allowed_age_ratings)
        where.append(f"age_rating IN ({q_marks2})")

    if exclude_ids:
        q_marks3 = ",".join("?" for _ in exclude_ids)
        where.append(f"id NOT IN ({q_marks3})")

    # Base query
    base_sql = f"""
        SELECT m.*
        FROM movies m
        {"WHERE " + " AND ".join(where) if where else ""}
    """

    # Genre filter (ANY match): join with movie_genres/genres via EXISTS
    extra_params: List[Any] = []
    if languages: extra_params += languages
    if allowed_age_ratings: extra_params += allowed_age_ratings
    if exclude_ids: extra_params += exclude_ids

    if genres_any:
        q_marks4 = ",".join("?" for _ in genres_any)
        base_sql = f"""
            SELECT m.*
            FROM movies m
            WHERE {" AND ".join(where)} AND EXISTS (
                SELECT 1 FROM movie_genres mg
                JOIN genres g ON g.id = mg.genre_id
                WHERE mg.movie_id = m.id AND g.name IN ({q_marks4})
            )
        """
        extra_params += genres_any

    # Execute the query with all parameters
    rows = con.execute(base_sql, tuple(params.values()) + tuple(extra_params)).fetchall()
    return rows