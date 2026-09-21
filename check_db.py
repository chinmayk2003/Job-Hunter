import sqlite3
from pathlib import Path
DB_PATH = Path('data/jobs.db')
conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM jobs')
print('Jobs:', cur.fetchone()[0])
cur.execute('SELECT COUNT(*) FROM analysis')
print('Analysis:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM analysis WHERE recommendation='strong'")
print('Strong:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM analysis WHERE recommendation='stretch'")
print('Stretch:', cur.fetchone()[0])
cur.execute('SELECT DISTINCT location FROM jobs LIMIT 30')
locs = [r[0] for r in cur.fetchall()]
print('Sample locations:', locs[:20])
cur.execute('SELECT title, location FROM jobs LIMIT 10')
for r in cur.fetchall():
    print(f'  {r[0]!r} | {r[1]!r}')
conn.close()
