import sqlite3
from pathlib import Path

sql = Path("schema.sql").read_text(encoding="utf-8")

con = sqlite3.connect("movies.db")
con.executescript(sql)
con.commit()
con.close()

print("movies.db initialized")