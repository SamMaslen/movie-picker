"""Movie Picker Web App using FastAPI.
A web interface to pick a movie to watch from a local database based on preferences.
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional
from db import connect
from movie_picker import Prefs, pick_movie_from_db

# App configuration
APP_TITLE = "Movie Picker"
DB_PATH = "movies.db"

# UK BBFC age ratings
UK_RATINGS = ["U", "PG", "12", "12A", "15", "18"]

# Language codes converted to names (for display)
LANG_MAP = {
    "en": "English", "fr": "French", "ja": "Japanese", "ko": "Korean", "es": "Spanish", "de": "German", "it": "Italian",
    "hi": "Hindi", "zh": "Chinese", "pt": "Portuguese", "ru": "Russian", "ar": "Arabic", "tr": "Turkish", "sv": "Swedish", 
    "nl": "Dutch",  "da": "Danish", "fi": "Finnish", "no": "Norwegian", "pl": "Polish", "cs": "Czech", "el": "Greek",
    "he": "Hebrew", "th": "Thai", "ro": "Romanian", "hu": "Hungarian", "vi": "Vietnamese", "id": "Indonesian", "fa": "Persian",
    "uk": "Ukrainian", "sr": "Serbian", "ca": "Catalan", "hr": "Croatian", "bg": "Bulgarian", "sl": "Slovenian",
    "lt": "Lithuanian", "lv": "Latvian", "et": "Estonian", "ms": "Malay", "eu": "Basque", "is": "Icelandic", "mt": "Maltese",
    "ga": "Irish", "cn": "Cantonese", "te": "Telugu",
}

app = FastAPI(title=APP_TITLE)

# Static files (CSS / images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Base URL for TMDB poster images (w342 size)
IMAGE_BASE = "https://image.tmdb.org/t/p/w342" 

# Helper to get all genres from DB for the genres dropdown
def get_all_genres() -> List[str]:
    con = connect(DB_PATH)
    rows = con.execute("SELECT name FROM genres ORDER BY name").fetchall()
    return [r["name"] for r in rows]

# Helper to get all languages from DB for the languages dropdown
def get_all_languages() -> list[str]:
    con = connect(DB_PATH)
    rows = con.execute("""
        SELECT language, COUNT(*) AS n
        FROM movies
        WHERE language IS NOT NULL AND TRIM(language) <> ''
        GROUP BY language
        ORDER BY n DESC
    """).fetchall()
    return [r["language"] for r in rows]

# Home page with filter form
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Initial filter form loads with no result
    genres = get_all_genres()
    context = {
        "request": request,
        "genres": genres,
        "languages": get_all_languages(),
        "defaults": {                        
            "ymin": 1970, "ymax": 2024,
            "rtmin": 80,  "rtmax": 160,
            "minr": 7.0,
            "ages": {a: True for a in UK_RATINGS},  # all selected by default
        },
        "selected_genres": set(),           
        "selected_languages": set(), 
        "result": None,         # no result yet
        "IMAGE_BASE": IMAGE_BASE,
        "LANG_MAP": LANG_MAP,
    }
    return templates.TemplateResponse("index.html", context)

# Form submission to pick a movie
@app.post("/pick", response_class=HTMLResponse)
async def pick(
    request: Request,
    genres: Optional[List[str]] = Form(default=None),
    ymin: int = Form(...),
    ymax: int = Form(...),
    rtmin: int = Form(...),
    rtmax: int = Form(...),
    minr: float = Form(...),
    languages: Optional[List[str]] = Form(default=None),
    # Age ratings checkboxes
    age_U: Optional[str] = Form(default=None),
    age_PG: Optional[str] = Form(default=None),
    age_12: Optional[str] = Form(default=None),
    age_12A: Optional[str] = Form(default=None),
    age_15: Optional[str] = Form(default=None),
    age_18: Optional[str] = Form(default=None),
):
    # Collect selected age ratings
    selected_ages = []
    if age_U: selected_ages.append("U")
    if age_PG: selected_ages.append("PG")
    if age_12: selected_ages.append("12")
    if age_12A: selected_ages.append("12A")
    if age_15: selected_ages.append("15")
    if age_18: selected_ages.append("18")
    if not selected_ages:
        selected_ages = UK_RATINGS[:]  

    # Clean up languages (strip whitespace, lowercase)
    langs = [c.strip().lower() for c in (languages or []) if c.strip()]

    # Build Prefs and get a movie
    prefs = Prefs(
        genres=genres or [],
        year_range=(ymin, ymax),
        runtime_range=(rtmin, rtmax),
        languages=langs,
        min_rating=minr,
        allowed_age_ratings=selected_ages,
    )

    # Get the movie recommendation
    result = pick_movie_from_db(prefs, db_path=DB_PATH)

    # Re-render the form with the result
    context = {
        "request": request,
        "genres": get_all_genres(),
        "languages": get_all_languages(),
        "defaults": {                         
            "ymin": ymin, "ymax": ymax,
            "rtmin": rtmin, "rtmax": rtmax,
            "minr": minr,
            "ages": {a: (a in selected_ages) for a in UK_RATINGS},
        },
        "selected_genres": set(genres or []),  
        "selected_languages": set(langs), 
        "result": result,
        "IMAGE_BASE": IMAGE_BASE,
        "LANG_MAP": LANG_MAP,
    }
    return templates.TemplateResponse("index.html", context)

# Simple JSON API 
@app.post("/api/pick", response_class=JSONResponse)
async def api_pick(payload: dict):
    # Build Prefs from JSON payload (with defaults)
    prefs = Prefs(
        genres=payload.get("genres", []),
        year_range=tuple(payload.get("year_range", [1970, 2024])),
        runtime_range=tuple(payload.get("runtime_range", [80, 160])),
        languages=payload.get("languages", []),
        min_rating=float(payload.get("min_rating", 7.0)),
        allowed_age_ratings=payload.get("allowed_age_ratings", UK_RATINGS),
    )
    return pick_movie_from_db(prefs, db_path=DB_PATH)