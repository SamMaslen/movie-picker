"""
Bulk seed your movie database from TMDb.

Edit the JOBS list to include whichever filters you want.

Example:
  ["--genres", "Action,Comedy", "--year-min", "2000", "--year-max", "2024", "--pages", "5"]
"""

import sys, subprocess, time

PY = sys.executable
SLEEP_BETWEEN = 1.0  # seconds between jobs to avoid hammering the API

# Base command (adjust module path if tmdb_fetch.py is at repo root)
BASE = [
    PY, "-m", "src.tmdb_fetch",
    "--db", "movies.db",
    "--vote-count-min", "1000",
    "--sort-by", "vote_count.desc"
]

# --------------------------------------------------------------------
# Example jobs — edit/add/remove to suit your needs
# --------------------------------------------------------------------
JOBS = [
    ["--genres", "Action,Science Fiction", "--year-min", "2000", "--year-max", "2024", "--pages", "5"],
    ["--genres", "Comedy,Romance", "--year-min", "1990", "--year-max", "1999", "--pages", "3"],
]

def run_job(args):
    cmd = BASE + args
    print("\n=== Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    time.sleep(SLEEP_BETWEEN)

if __name__ == "__main__":
    for job in JOBS:
        run_job(job)
    print("\nDone seeding.")