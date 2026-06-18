import os
import sys
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'booktop-secret-2024')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = DATABASE_URL.startswith('postgres')

# ── Database helpers ──────────────────────────────────────────────────────────

def _parse_pg_url(url):
    from urllib.parse import urlparse, parse_qs
    import ssl
    url = url.replace('postgres://', 'postgresql://', 1)
    p = urlparse(url)
    qs = parse_qs(p.query)
    ssl_ctx = None
    if qs.get('sslmode', [''])[0] == 'require':
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
    return dict(host=p.hostname, port=p.port or 5432,
                database=p.path.lstrip('/'), user=p.username,
                password=p.password, ssl_context=ssl_ctx)


def get_db():
    if 'db' not in g:
        if USE_POSTGRES:
            import pg8000.dbapi as pg
            g.db = pg.connect(**_parse_pg_url(DATABASE_URL))
            g.db_type = 'postgres'
        else:
            import sqlite3
            conn = sqlite3.connect('booktop.db')
            conn.row_factory = sqlite3.Row
            g.db = conn
            g.db_type = 'sqlite'
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    conn = g.pop('db', None)
    if conn:
        try:
            conn.close()
        except Exception:
            pass


def _cur_rows(cur):
    if cur.description is None:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def query(sql, params=(), one=False):
    conn = get_db()
    if g.db_type == 'postgres':
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = _cur_rows(cur)
        if one:
            return rows[0] if rows else None
        return rows
    else:
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        if one:
            return rows[0] if rows else None
        return rows


def execute(sql, params=()):
    conn = get_db()
    if g.db_type == 'postgres':
        cur = conn.cursor()
        cur.execute(sql, params)
    else:
        conn.execute(sql, params)


def lastrowid(sql, params=()):
    conn = get_db()
    if g.db_type == 'postgres':
        cur = conn.cursor()
        cur.execute(sql + ' RETURNING id', params)
        return cur.fetchone()[0]
    else:
        cur = conn.execute(sql, params)
        return cur.lastrowid


def commit():
    get_db().commit()


# ── Schema & seed ─────────────────────────────────────────────────────────────

def init_db():
    if USE_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite()
    commit()
    _seed_data()


def _init_postgres():
    stmts = [
        '''CREATE TABLE IF NOT EXISTS razredi (
            id SERIAL PRIMARY KEY, naziv TEXT NOT NULL,
            razina INTEGER NOT NULL, skolska_godina TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS predmeti (
            id SERIAL PRIMARY KEY, naziv TEXT NOT NULL, razina INTEGER NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS korisnici (
            id SERIAL PRIMARY KEY, ime TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, lozinka TEXT NOT NULL,
            uloga TEXT NOT NULL, razred_id INTEGER REFERENCES razredi(id))''',
        '''CREATE TABLE IF NOT EXISTS vraceno (
            id SERIAL PRIMARY KEY,
            razred_id INTEGER NOT NULL REFERENCES razredi(id),
            predmet_id INTEGER NOT NULL REFERENCES predmeti(id),
            kolicina INTEGER NOT NULL DEFAULT 0, skolska_godina TEXT NOT NULL,
            korisnik_id INTEGER REFERENCES korisnici(id),
            datum DATE DEFAULT CURRENT_DATE,
            UNIQUE(razred_id, predmet_id, skolska_godina))''',
        '''CREATE TABLE IF NOT EXISTS rezerva (
            id SERIAL PRIMARY KEY, razina INTEGER NOT NULL,
            predmet_id INTEGER NOT NULL REFERENCES predmeti(id),
            kolicina INTEGER NOT NULL DEFAULT 0, skolska_godina TEXT NOT NULL,
            UNIQUE(razina, predmet_id, skolska_godina))''',
        '''CREATE TABLE IF NOT EXISTS upisi (
            id SERIAL PRIMARY KEY, razina INTEGER NOT NULL,
            broj_ucenika INTEGER NOT NULL DEFAULT 0, skolska_godina TEXT NOT NULL,
            UNIQUE(razina, skolska_godina))''',
    ]
    for stmt in stmts:
        execute(stmt)


def _init_sqlite():
    get_db().executescript('''
        CREATE TABLE IF NOT EXISTS razredi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naziv TEXT NOT NULL, razina INTEGER NOT NULL, skolska_godina TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS predmeti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naziv TEXT NOT NULL, razina INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS korisnici (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ime TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, lozinka TEXT NOT NULL,
            uloga TEXT NOT NULL, razred_id INTEGER REFERENCES razredi(id));
        CREATE TABLE IF NOT EXISTS vraceno (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razred_id INTEGER NOT NULL, predmet_id INTEGER NOT NULL,
            kolicina INTEGER NOT NULL DEFAULT 0, skolska_godina TEXT NOT NULL,
            korisnik_id INTEGER, datum TEXT DEFAULT (date('now')),
            UNIQUE(razred_id, predmet_id, skolska_godina));
        CREATE TABLE IF NOT EXISTS rezerva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razina INTEGER NOT NULL, predmet_id INTEGER NOT NULL,
            kolicina INTEGER NOT NULL DEFAULT 0, skolska_godina TEXT NOT NULL,
            UNIQUE(razina, predmet_id, skolska_godina));
        CREATE TABLE IF NOT EXISTS upisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT, razina INTEGER NOT NULL,
            broj_ucenika INTEGER NOT NULL DEFAULT 0, skolska_godina TEXT NOT NULL,
            UNIQUE(razina, skolska_godina));
    ''')


def _seed_data():
    from werkzeug.security import generate_password_hash
    ph = '%s' if USE_POSTGRES else '?'
    row = query(f'SELECT COUNT(*) AS c FROM korisnici', one=True)
    if row and int(row['c']) > 0:
        return

    godina = '2025/2026'
    razred_ids = {}
    for r in range(1, 9):
        for o in ['A', 'B', 'C']:
            rid = lastrowid(
                f'INSERT INTO razredi (naziv, razina, skolska_godina) VALUES ({ph},{ph},{ph})',
                (f'{r}.{o}', r, godina))
            razred_ids[(r, o)] = rid

    predmeti_po_razini = {
        1: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura'],
        2: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura'],
        3: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura', 'Engleski jezik'],
        4: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura', 'Engleski jezik'],
        5: ['Hrvatski jezik', 'Matematika', 'Priroda', 'Geografija', 'Povijest', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura', 'Engleski jezik', 'Informatika'],
        6: ['Hrvatski jezik', 'Matematika', 'Priroda', 'Geografija', 'Povijest', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura', 'Engleski jezik', 'Informatika'],
        7: ['Hrvatski jezik', 'Matematika', 'Fizika', 'Kemija', 'Biologija', 'Geografija', 'Povijest', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura', 'Engleski jezik', 'Informatika'],
        8: ['Hrvatski jezik', 'Matematika', 'Fizika', 'Kemija', 'Biologija', 'Geografija', 'Povijest', 'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura', 'Engleski jezik', 'Informatika'],
    }

    predmet_ids = {}
    for razina, predmeti in predmeti_po_razini.items():
        for naziv in predmeti:
            key = (naziv, razina)
            if key not in predmet_ids:
                pid = lastrowid(
                    f'INSERT INTO predmeti (naziv, razina) VALUES ({ph},{ph})',
                    (naziv, razina))
                predmet_ids[key] = pid

    admin_pass = generate_password_hash('admin123')
    execute(f'INSERT INTO korisnici (ime, email, lozinka, uloga) VALUES ({ph},{ph},{ph},{ph})',
            ('Knjižničarka', 'admin@skola.hr', admin_pass, 'administrator'))

    razrednik_data = [
        ('Marija Kovač',     'razrednik1a@skola.hr', (1,'A')),
        ('Ivan Horvat',      'razrednik1b@skola.hr', (1,'B')),
        ('Ana Perić',        'razrednik1c@skola.hr', (1,'C')),
        ('Petra Novak',      'razrednik2a@skola.hr', (2,'A')),
        ('Josip Babić',      'razrednik2b@skola.hr', (2,'B')),
        ('Lucija Tomić',     'razrednik2c@skola.hr', (2,'C')),
        ('Tomislav Jurić',   'razrednik3a@skola.hr', (3,'A')),
        ('Sandra Marić',     'razrednik3b@skola.hr', (3,'B')),
        ('Damir Vidović',    'razrednik3c@skola.hr', (3,'C')),
        ('Vesna Blažić',     'razrednik4a@skola.hr', (4,'A')),
        ('Nikola Pavić',     'razrednik4b@skola.hr', (4,'B')),
        ('Kristina Vuković', 'razrednik4c@skola.hr', (4,'C')),
        ('Mario Filipović',  'razrednik5a@skola.hr', (5,'A')),
        ('Đurđica Knežević', 'razrednik5b@skola.hr', (5,'B')),
        ('Stjepan Majić',    'razrednik5c@skola.hr', (5,'C')),
        ('Mirela Lončar',    'razrednik6a@skola.hr', (6,'A')),
        ('Dragan Šimić',     'razrednik6b@skola.hr', (6,'B')),
        ('Renata Bogdanović','razrednik6c@skola.hr', (6,'C')),
        ('Zlatko Đukić',     'razrednik7a@skola.hr', (7,'A')),
        ('Helena Miletić',   'razrednik7b@skola.hr', (7,'B')),
        ('Krešimir Rukavina','razrednik7c@skola.hr', (7,'C')),
        ('Dijana Galić',     'razrednik8a@skola.hr', (8,'A')),
        ('Boris Živković',   'razrednik8b@skola.hr', (8,'B')),
        ('Tatjana Radić',    'razrednik8c@skola.hr', (8,'C')),
    ]
    lozinka = generate_password_hash('razrednik123')
    for ime, email, (razina, odj) in razrednik_data:
        execute(
            f'INSERT INTO korisnici (ime, email, lozinka, uloga, razred_id) VALUES ({ph},{ph},{ph},{ph},{ph})',
            (ime, email, lozinka, 'razrednik', razred_ids[(razina, odj)]))
    commit()


# ── Init on startup ───────────────────────────────────────────────────────────
# Runs once when the module loads (each Vercel function instance)
_init_error = None
try:
    with app.app_context():
        init_db()
except Exception as _e:
    _init_error = str(_e)
    print(f"[booktop] DB init error: {_e}", file=sys.stderr)


# ── Auth decorators ───────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'korisnik_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'korisnik_id' not in session:
            return redirect(url_for('login'))
        if session.get('uloga') != 'administrator':
            flash('Nemate ovlasti za pristup toj stranici.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated


def _tekuca_godina():
    row = query('SELECT skolska_godina FROM razredi LIMIT 1', one=True)
    return row['skolska_godina'] if row else '2025/2026'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'korisnik_id' not in session:
        return redirect(url_for('login'))
    if session['uloga'] == 'administrator':
        return redirect(url_for('rezerva'))
    return redirect(url_for('moj_razred'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    from werkzeug.security import check_password_hash
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        lozinka = request.form['lozinka']
        ph = '%s' if USE_POSTGRES else '?'
        korisnik = query(
            f'SELECT * FROM korisnici WHERE LOWER(email) = {ph}', (email,), one=True)
        if korisnik and check_password_hash(korisnik['lozinka'], lozinka):
            session['korisnik_id'] = korisnik['id']
            session['ime'] = korisnik['ime']
            session['uloga'] = korisnik['uloga']
            session['razred_id'] = korisnik['razred_id']
            return redirect(url_for('index'))
        flash('Pogrešan email ili lozinka.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/moj-razred', methods=['GET', 'POST'])
@login_required
def moj_razred():
    if session['uloga'] != 'razrednik':
        return redirect(url_for('index'))

    ph = '%s' if USE_POSTGRES else '?'
    razred_id = session['razred_id']
    razred = query(f'SELECT * FROM razredi WHERE id = {ph}', (razred_id,), one=True)
    if not razred:
        flash('Razred nije pronađen.', 'danger')
        return redirect(url_for('logout'))

    godina = razred['skolska_godina']
    predmeti = query(
        f'SELECT * FROM predmeti WHERE razina = {ph} ORDER BY naziv', (razred['razina'],))

    if request.method == 'POST':
        for predmet in predmeti:
            kolicina = int(request.form.get(f'v_{predmet["id"]}', 0) or 0)
            if USE_POSTGRES:
                execute('''
                    INSERT INTO vraceno (razred_id, predmet_id, kolicina, skolska_godina, korisnik_id, datum)
                    VALUES (%s,%s,%s,%s,%s,CURRENT_DATE)
                    ON CONFLICT(razred_id, predmet_id, skolska_godina)
                    DO UPDATE SET kolicina=EXCLUDED.kolicina, korisnik_id=EXCLUDED.korisnik_id, datum=CURRENT_DATE
                ''', (razred_id, predmet['id'], kolicina, godina, session['korisnik_id']))
            else:
                execute('''
                    INSERT INTO vraceno (razred_id, predmet_id, kolicina, skolska_godina, korisnik_id, datum)
                    VALUES (?,?,?,?,?,date('now'))
                    ON CONFLICT(razred_id, predmet_id, skolska_godina)
                    DO UPDATE SET kolicina=excluded.kolicina, korisnik_id=excluded.korisnik_id, datum=excluded.datum
                ''', (razred_id, predmet['id'], kolicina, godina, session['korisnik_id']))
        commit()
        flash('Podaci su uspješno spremljeni.', 'success')
        return redirect(url_for('moj_razred'))

    vraceno_map = {
        row['predmet_id']: row['kolicina']
        for row in query(
            f'SELECT predmet_id, kolicina FROM vraceno WHERE razred_id={ph} AND skolska_godina={ph}',
            (razred_id, godina))
    }
    return render_template('moj_razred.html', razred=razred, predmeti=predmeti,
                           vraceno_map=vraceno_map, godina=godina)


@app.route('/rezerva', methods=['GET', 'POST'])
@admin_required
def rezerva():
    ph = '%s' if USE_POSTGRES else '?'
    razine = list(range(1, 9))
    godina = _tekuca_godina()

    if request.method == 'POST':
        for razina in razine:
            predmeti = query(f'SELECT * FROM predmeti WHERE razina={ph}', (razina,))
            for predmet in predmeti:
                kolicina = int(request.form.get(f'o_{razina}_{predmet["id"]}', 0) or 0)
                execute(
                    f'INSERT INTO rezerva (razina,predmet_id,kolicina,skolska_godina) VALUES ({ph},{ph},{ph},{ph})'
                    f' ON CONFLICT(razina,predmet_id,skolska_godina) DO UPDATE SET kolicina=EXCLUDED.kolicina',
                    (razina, predmet['id'], kolicina, godina))
        commit()
        flash('Rezerva je uspješno spremljena.', 'success')
        return redirect(url_for('rezerva'))

    data = {}
    for razina in razine:
        predmeti = query(f'SELECT * FROM predmeti WHERE razina={ph} ORDER BY naziv', (razina,))
        rezerve = {
            row['predmet_id']: row['kolicina']
            for row in query(
                f'SELECT predmet_id, kolicina FROM rezerva WHERE razina={ph} AND skolska_godina={ph}',
                (razina, godina))
        }
        data[razina] = {'predmeti': predmeti, 'rezerve': rezerve}
    return render_template('rezerva.html', data=data, razine=razine, godina=godina)


@app.route('/upisi', methods=['GET', 'POST'])
@admin_required
def upisi():
    ph = '%s' if USE_POSTGRES else '?'
    razine = list(range(1, 9))
    godina = _tekuca_godina()

    if request.method == 'POST':
        for razina in razine:
            broj = int(request.form.get(f'n_{razina}', 0) or 0)
            execute(
                f'INSERT INTO upisi (razina,broj_ucenika,skolska_godina) VALUES ({ph},{ph},{ph})'
                f' ON CONFLICT(razina,skolska_godina) DO UPDATE SET broj_ucenika=EXCLUDED.broj_ucenika',
                (razina, broj, godina))
        commit()
        flash('Broj upisanih učenika je uspješno spremljen.', 'success')
        return redirect(url_for('upisi'))

    upisi_map = {
        row['razina']: row['broj_ucenika']
        for row in query(f'SELECT razina, broj_ucenika FROM upisi WHERE skolska_godina={ph}', (godina,))
    }
    return render_template('upisi.html', razine=razine, upisi_map=upisi_map, godina=godina)


@app.route('/izvjestaj')
@admin_required
def izvjestaj():
    ph = '%s' if USE_POSTGRES else '?'
    godina = _tekuca_godina()
    razine = list(range(1, 9))

    upisi_map = {
        row['razina']: row['broj_ucenika']
        for row in query(f'SELECT razina, broj_ucenika FROM upisi WHERE skolska_godina={ph}', (godina,))
    }
    rezerva_map = {
        (row['razina'], row['predmet_id']): row['kolicina']
        for row in query(f'SELECT razina, predmet_id, kolicina FROM rezerva WHERE skolska_godina={ph}', (godina,))
    }
    vraceno_po_razini = {
        (row['razina'], row['predmet_id']): row['ukupno']
        for row in query(f'''
            SELECT r.razina, v.predmet_id, SUM(v.kolicina) AS ukupno
            FROM vraceno v JOIN razredi r ON v.razred_id=r.id
            WHERE v.skolska_godina={ph}
            GROUP BY r.razina, v.predmet_id
        ''', (godina,))
    }

    izvjestaj_data, narudzba = [], []
    for razina in razine:
        predmeti = query(f'SELECT * FROM predmeti WHERE razina={ph} ORDER BY naziv', (razina,))
        n = upisi_map.get(razina, 0)
        redovi = []
        for predmet in predmeti:
            v = vraceno_po_razini.get((razina, predmet['id']), 0)
            o = rezerva_map.get((razina, predmet['id']), 0)
            x = max(0, n - (v + o))
            redovi.append({'predmet': predmet['naziv'], 'predmet_id': predmet['id'],
                           'v': v, 'o': o, 'n': n, 'x': x})
            if x > 0:
                narudzba.append({'razina': razina, 'predmet': predmet['naziv'],
                                 'predmet_id': predmet['id'], 'x': x})
        izvjestaj_data.append({'razina': razina, 'n': n, 'redovi': redovi})

    return render_template('izvjestaj.html', izvjestaj_data=izvjestaj_data,
                           narudzba=narudzba, godina=godina)


@app.route('/korisnici')
@admin_required
def korisnici():
    svi = query('''
        SELECT k.id, k.ime, k.email, k.uloga, r.naziv AS razred_naziv
        FROM korisnici k LEFT JOIN razredi r ON k.razred_id=r.id
        ORDER BY k.uloga, k.ime
    ''')
    return render_template('korisnici.html', korisnici=svi)


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
