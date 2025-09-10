🎬 Movie Picker

A web application that allows the user to get a movie suggestion based on their preferences.

Powered by [FastAPI](https://fastapi.tiangolo.com/), [TMDB](https://www.themoviedb.org/) data, and a local SQLite database. 

Tech Stack

- Backend: [FastAPI](https://fastapi.tiangolo.com/)  
- Frontend: Jinja2 templates + custom CSS  
- Database: SQLite  
- APIs: [TMDB](https://developers.themoviedb.org/) (requires API key)  
- Other: python-dotenv, requests 

Project Structure

├── app.py # FastAPI entrypoint (routes, template rendering)
├── movie_picker.py # Core picking logic (scoring, weighted random)
├── tmdb_fetch.py # CLI tool for seeding SQLite with TMDB movies
├── db.py # DB helpers (connect, upsert_movie, get_candidates, etc.)
├── movies.db # SQLite database (created after seeding)
├── templates/
│ └── index.html # Web UI template
├── static/
│ ├── style.css # CSS styling
│ └── bbfc/ # BBFC age rating icons (U, PG, 12, 12A, 15, 18)
└── README.md # This file

Setup

1. Clone the repo
   ```bash
   git clone https://github.com/sammaslen/projects/movie-picker.git
   cd movie-picker

2. Create a virtual environment
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows

3. Install dependencies
   pip install -r requirements.txt

4. Set your TMDB API key
   Create a file tmdb.env in the project root:
   TMDB_API_KEY=your_tmdb_api_key_here

Seed the Database

Run bulk_seed.py to seed the database. Make any tweaks you like to choose which type of films it gets.

Run the app

   uvicorn app:app --reload
Then open your browser at http://127.0.0.1:8000/

Screenshots

- **Filter form:**
  ![filters screenshot](docs/filters.png)

- **Result card:**
  ![result screenshot](docs/result.png)

