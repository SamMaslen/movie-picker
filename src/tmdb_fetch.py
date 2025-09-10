# Fetch movies from TMDB and store in a local SQLite database.

import os, sys, time, json, argparse
from typing import Dict, List, Optional, Tuple
import requests
from db import connect, upsert_movie
from dotenv import load_dotenv

# Load TMDB API key from environment variable or .env file
load_dotenv(dotenv_path="tmdb.env")

TMDB_API = "https://api.themoviedb.org/3"

UK_RATINGS_ORDER = ["U", "PG", "12", "12A", "15", "18"] 
UK_RATINGS_SET = set(UK_RATINGS_ORDER)

# Fetch data from TMDB with proper authentication
def tmdb_get(path: str, params: Dict) -> Dict:
    key = os.environ.get("TMDB_API_KEY")
    if not key:
        print("ERROR: TMDB_API_KEY env var not set.", file=sys.stderr)
        sys.exit(1)
    headers = {"Authorization": f"Bearer {key}"} if key.startswith("eyJ") else None
    if headers:
        # v4 auth (Bearer)
        r = requests.get(f"{TMDB_API}{path}", params=params, headers=headers, timeout=20)
    else:
        # v3 key in query string
        params = dict(params or {})
        params["api_key"] = key
        r = requests.get(f"{TMDB_API}{path}", params=params, timeout=20)
    r.raise_for_status()
    return r.json()

# Fetch TMDB genres mapping {id: name}
def fetch_genres() -> Dict[int, str]:
    data = tmdb_get("/genre/movie/list", {"language": "en-GB"})
    return {g["id"]: g["name"] for g in data.get("genres", [])}

# Fetch the runtime of a movie by its TMDB ID
def fetch_runtime(movie_id: int) -> Optional[int]:
    data = tmdb_get(f"/movie/{movie_id}", {"language": "en-GB"})
    return data.get("runtime")

# Pick the UK (BBFC) certification from the release dates data
def pick_gb_certification(release_dates: Dict) -> Optional[str]:
    """
    TMDB returns a structure with results per country. We pick GB → best certification.
    Prefer a non-empty certification; if multiple, choose the most restrictive (highest in UK order).
    If none, return None.
    """
    for entry in release_dates.get("results", []):
        if entry.get("iso_3166_1") == "GB":
            certs = [rd.get("certification", "").strip() for rd in entry.get("release_dates", [])]
            certs = [c for c in certs if c]  # non-empty
            if not certs:
                return None
            # Normalise weird variants occasionally seen (e.g., "12 A", "R18", etc.)
            normalised = [normalise_uk_cert(c) for c in certs if normalise_uk_cert(c)]
            if not normalised:
                return None
            # choose the most restrictive (e.g. if both "PG" and "12A" appear, pick "12A")
            idx = max(UK_RATINGS_ORDER.index(c) for c in normalised)
            return UK_RATINGS_ORDER[idx]
    return None

def normalise_uk_cert(cert: str) -> Optional[str]:
    c = cert.upper().replace(" ", "")
    # Common variants mapping
    if c in {"U", "PG", "12", "12A", "15", "18"}:
        return c
    # Filter out anomalies to set standard certifications
    if c.startswith("12A"):
        return "12A"
    if c.startswith("12"):
        return "12"
    if c.startswith("PG"):
        return "PG"
    if c.startswith("U"):
        return "U"
    if c.startswith("18"):
        return "18"
    if c.startswith("15"):
        return "15"
    return None

# Discover movies with given filters
def discover_page(
    page: int,
    with_genre_ids: Optional[List[int]],
    year_min: Optional[int],
    year_max: Optional[int],
    runtime_min: Optional[int],
    runtime_max: Optional[int],
    language: Optional[str],
    sort_by: str,
    vote_count_min: Optional[int],
) -> Dict:
    params = {
        "language": "en-GB",
        "sort_by": sort_by,
        "include_adult": "false",
        "include_video": "false",
        "page": page,
        "watch_region": "GB",
    }
    if with_genre_ids:
        params["with_genres"] = ",".join(str(g) for g in with_genre_ids)
    if year_min:
        params["primary_release_date.gte"] = f"{year_min}-01-01"
    if year_max:
        params["primary_release_date.lte"] = f"{year_max}-12-31"
    if runtime_min is not None:
        params["with_runtime.gte"] = str(runtime_min)
    if runtime_max is not None:
        params["with_runtime.lte"] = str(runtime_max)
    if language:
        params["with_original_language"] = language
    if vote_count_min is not None:
        params["vote_count.gte"] = vote_count_min

    return tmdb_get("/discover/movie", params)

# Fetch UK (GB) release dates and return the certification
def fetch_gb_release_dates(movie_id: int) -> Optional[str]:
    data = tmdb_get(f"/movie/{movie_id}/release_dates", {})
    return pick_gb_certification(data)

# Main function for seeding/updating the SQLite database with movies from TMDB.
def main():
    ap = argparse.ArgumentParser(description="Seed SQLite with TMDB movies and UK (BBFC) age ratings.")
    ap.add_argument("--db", default="movies.db")
    ap.add_argument("--genres", default="", help="Comma-separated genre names to include (ANY). Example: Action,Sci-Fi")
    ap.add_argument("--pages", type=int, default=2, help="How many TMDB discover pages to fetch (20 per page).")
    ap.add_argument("--year-min", type=int, default=None)
    ap.add_argument("--year-max", type=int, default=None)
    ap.add_argument("--runtime-min", type=int, default=None)
    ap.add_argument("--runtime-max", type=int, default=None)
    ap.add_argument("--original-language", default=None, help="e.g., en, ja, ko. Leave empty for any.")
    ap.add_argument("--sleep", type=float, default=0.25, help="Sleep between API calls (seconds).")
    ap.add_argument("--vote-count-min", type=int, default=500, help="Minimum TMDB vote_count to include")
    ap.add_argument("--sort-by", default="vote_count.desc",
                    help="TMDB sort_by, e.g. vote_count.desc, vote_average.desc, popularity.desc")
    args = ap.parse_args()

    con = connect(args.db)

    genre_map = fetch_genres()  # {id: name}
    name_to_id = {v.lower(): k for k, v in genre_map.items()}

    with_genre_ids: Optional[List[int]] = None
    if args.genres.strip():
        wanted = [g.strip().lower() for g in args.genres.split(",")]
        missing = [g for g in wanted if g not in name_to_id]
        if missing:
            print(f"WARNING: Unknown TMDB genre names: {missing}. Available: {sorted(genre_map.values())}")
        with_genre_ids = [name_to_id[g] for g in wanted if g in name_to_id]

    total_upserted = 0

    # Fetch and process pages of results
    for page in range(1, args.pages + 1):
        disc = discover_page(
            page=page,
            with_genre_ids=with_genre_ids,
            year_min=args.year_min,
            year_max=args.year_max,
            runtime_min=args.runtime_min,
            runtime_max=args.runtime_max,
            language=args.original_language,
            sort_by=args.sort_by,
            vote_count_min=args.vote_count_min,
        )
        results = disc.get("results", [])
        if not results:
            print(f"Page {page}: no results.")
            break

        # Fetch the runtime and UK age rating for each movie, then upsert into DB
        for m in results:
            tmdb_id = int(m["id"])
            # Get UK age rating (BBFC)
            try:
                age_rating = fetch_gb_release_dates(tmdb_id)
                time.sleep(args.sleep)
            except requests.HTTPError as e:
                print(f"Release dates error for {tmdb_id}: {e}", file=sys.stderr)
                age_rating = None

            try:
                runtime = fetch_runtime(tmdb_id)
                time.sleep(args.sleep)  # avoid hitting rate limits
            except Exception as e:
                print(f"Runtime fetch failed for {tmdb_id}: {e}")
                runtime = None

            # Prepare movie row for upsert
            movie_row = {
                "id": tmdb_id,
                "title": m.get("title") or m.get("original_title"),
                "year": int((m.get("release_date") or "0000-00-00")[:4]) if m.get("release_date") else None,
                "runtime": runtime,
                "language": m.get("original_language"),
                "rating": float(m.get("vote_average") or 0.0),
                "age_rating": age_rating,
                "poster_path": m.get("poster_path"),
                "overview": m.get("overview"),
                "source_json": json.dumps(m),   # store full original data
            }

            # Get genres for the movie from genre_ids field in TMDB data
            gids = m.get("genre_ids", []) or []
            genres = [(gid, genre_map.get(gid, f"Genre {gid}")) for gid in gids]

            # Upsert into DB
            upsert_movie(con, movie_row, genres)
            total_upserted += 1

        print(f"Fetched page {page}: {len(results)} results. Upserted so far: {total_upserted}.")
        time.sleep(args.sleep)

    print(f"Done. Total upserted: {total_upserted}")

if __name__ == "__main__":
    main()