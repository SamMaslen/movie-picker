PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS movies (
  id          INTEGER PRIMARY KEY,
  title       TEXT NOT NULL,
  year        INTEGER,
  runtime     INTEGER,
  language    TEXT,
  rating      REAL,
  age_rating  TEXT,
  poster_path TEXT,
  overview    TEXT,
  source_json TEXT
);

CREATE TABLE IF NOT EXISTS genres (
  id   INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS movie_genres (
  movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
  genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
  PRIMARY KEY (movie_id, genre_id)
);

CREATE TABLE IF NOT EXISTS history (
  user_id   INTEGER NOT NULL DEFAULT 1,
  movie_id  INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
  picked_at TEXT NOT NULL,
  PRIMARY KEY (user_id, movie_id, picked_at)
);

CREATE INDEX IF NOT EXISTS idx_movies_year        ON movies(year);
CREATE INDEX IF NOT EXISTS idx_movies_runtime     ON movies(runtime);
CREATE INDEX IF NOT EXISTS idx_movies_language    ON movies(language);
CREATE INDEX IF NOT EXISTS idx_movies_rating      ON movies(rating);
CREATE INDEX IF NOT EXISTS idx_movies_age_rating  ON movies(age_rating);
CREATE INDEX IF NOT EXISTS idx_movie_genres_genre ON movie_genres(genre_id);