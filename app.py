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
            if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
                raise RuntimeError(
                    'DATABASE_URL nije postavljen! Dodajte PostgreSQL (Neon) vezu '
                    'u Vercel Environment Variables pod imenom DATABASE_URL.'
                )
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

PREDMETI_PO_RAZINI = {
    1: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    2: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    3: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Engleski jezik', 'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    4: ['Hrvatski jezik', 'Matematika', 'Priroda i društvo',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Engleski jezik', 'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    5: ['Hrvatski jezik', 'Hrvatski jezik 2', 'Matematika', 'Matematika 2',
        'Priroda', 'Geografija', 'Povijest',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Tehnička kultura', 'Engleski jezik', 'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    6: ['Hrvatski jezik', 'Hrvatski jezik 2', 'Matematika', 'Matematika 2',
        'Priroda', 'Geografija', 'Povijest',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Tehnička kultura', 'Engleski jezik', 'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    7: ['Hrvatski jezik', 'Hrvatski jezik 2', 'Matematika', 'Matematika 2',
        'Fizika', 'Kemija', 'Biologija', 'Geografija', 'Povijest',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Tehnička kultura', 'Engleski jezik', 'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
    8: ['Hrvatski jezik', 'Hrvatski jezik 2', 'Matematika', 'Matematika 2',
        'Fizika', 'Kemija', 'Biologija', 'Geografija', 'Povijest',
        'Likovna kultura', 'Glazbena kultura', 'Tjelesna i zdravstvena kultura',
        'Tehnička kultura', 'Engleski jezik', 'Informatika', '2. jezik',
        'Katolički vjeronauk', 'Pravoslavni vjeronauk', 'Islamski vjeronauk'],
}


def init_db():
    if USE_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite()
    commit()
    _seed_data()
    _ensure_predmeti()


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

    godina = '2025/2026'

    # Razredi — insert only if not already there
    existing_razredi = {
        r['naziv'] for r in query(f'SELECT naziv FROM razredi WHERE skolska_godina={ph}', (godina,))
    }
    for r in range(1, 9):
        for o in ['A', 'B', 'C']:
            naziv = f'{r}.{o}'
            if naziv not in existing_razredi:
                lastrowid(
                    f'INSERT INTO razredi (naziv, razina, skolska_godina) VALUES ({ph},{ph},{ph})',
                    (naziv, r, godina))

    # Predmeti — handled by _ensure_predmeti(), skip here

    # Admin account — idempotent insert
    admin_exists = query(f'SELECT id FROM korisnici WHERE email={ph}', ('admin@skola.hr',), one=True)
    if not admin_exists:
        admin_pass = generate_password_hash('admin123')
        execute(
            f'INSERT INTO korisnici (ime, email, lozinka, uloga) VALUES ({ph},{ph},{ph},{ph})',
            ('Knjižničarka', 'admin@skola.hr', admin_pass, 'administrator'))
    commit()


def _ensure_predmeti():
    """Sync subjects: add missing, remove ones no longer in the list."""
    ph = '%s' if USE_POSTGRES else '?'

    # Build expected set
    expected = {
        (naziv, razina)
        for razina, predmeti in PREDMETI_PO_RAZINI.items()
        for naziv in predmeti
    }

    # Add missing
    existing = set(
        (r['naziv'], r['razina'])
        for r in query('SELECT naziv, razina FROM predmeti')
    )
    for naziv, razina in expected - existing:
        execute(
            f'INSERT INTO predmeti (naziv, razina) VALUES ({ph},{ph})',
            (naziv, razina))

    # Remove subjects no longer in the list (only if they have no vraceno data)
    for naziv, razina in existing - expected:
        row = query(
            f'SELECT COUNT(*) AS c FROM vraceno v '
            f'JOIN predmeti p ON v.predmet_id=p.id '
            f'WHERE p.naziv={ph} AND p.razina={ph}',
            (naziv, razina), one=True)
        if row and int(row['c']) == 0:
            execute(
                f'DELETE FROM predmeti WHERE naziv={ph} AND razina={ph}',
                (naziv, razina))

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
    row = query('SELECT skolska_godina FROM razredi ORDER BY skolska_godina DESC LIMIT 1', one=True)
    return row['skolska_godina'] if row else '2025/2026'


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/debug-init')
def debug_init():
    info = {
        'USE_POSTGRES': USE_POSTGRES,
        'DATABASE_URL_set': bool(DATABASE_URL),
        'DATABASE_URL_prefix': (DATABASE_URL[:40] + '...') if len(DATABASE_URL) > 40 else (DATABASE_URL or '(NIJE POSTAVLJEN)'),
        'VERCEL_ENV': os.environ.get('VERCEL_ENV', 'nije postavljeno'),
        'init_error': _init_error or 'nema greske',
    }
    if not _init_error:
        try:
            info['korisnici_u_bazi'] = query('SELECT COUNT(*) AS c FROM korisnici', one=True)['c']
            info['predmeti_u_bazi'] = query('SELECT COUNT(*) AS c FROM predmeti', one=True)['c']
        except Exception as e:
            info['query_error'] = str(e)
    lines = '\n'.join(f'{k}: {v}' for k, v in info.items())
    return f'<pre style="font-size:16px;padding:20px">{lines}</pre>'


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


@app.route('/korisnici/novi', methods=['GET', 'POST'])
@admin_required
def novi_korisnik():
    from werkzeug.security import generate_password_hash
    ph = '%s' if USE_POSTGRES else '?'
    godina = _tekuca_godina()
    razredi = query(
        f'SELECT * FROM razredi WHERE skolska_godina={ph} ORDER BY razina, naziv',
        (godina,))

    if request.method == 'POST':
        ime = request.form['ime'].strip()
        email = request.form['email'].strip().lower()
        lozinka = request.form['lozinka']
        uloga = request.form['uloga']
        razred_id = request.form.get('razred_id') or None
        if razred_id:
            razred_id = int(razred_id)

        if not ime or not email or not lozinka:
            flash('Ime, email i lozinka su obavezni.', 'danger')
        else:
            hashed = generate_password_hash(lozinka)
            try:
                execute(
                    f'INSERT INTO korisnici (ime, email, lozinka, uloga, razred_id) VALUES ({ph},{ph},{ph},{ph},{ph})',
                    (ime, email, hashed, uloga, razred_id))
                commit()
                flash('Korisnik je uspješno dodan.', 'success')
                return redirect(url_for('korisnici'))
            except Exception as e:
                flash(f'Greška: email već postoji ili drugi problem. ({e})', 'danger')

    return render_template('korisnik_forma.html', korisnik=None, razredi=razredi, akcija='novi')


@app.route('/korisnici/uredi/<int:id>', methods=['GET', 'POST'])
@admin_required
def uredi_korisnik(id):
    from werkzeug.security import generate_password_hash
    ph = '%s' if USE_POSTGRES else '?'
    korisnik = query(f'SELECT * FROM korisnici WHERE id={ph}', (id,), one=True)
    if not korisnik:
        flash('Korisnik nije pronađen.', 'danger')
        return redirect(url_for('korisnici'))

    godina = _tekuca_godina()
    razredi = query(
        f'SELECT * FROM razredi WHERE skolska_godina={ph} ORDER BY razina, naziv',
        (godina,))

    if request.method == 'POST':
        ime = request.form['ime'].strip()
        email = request.form['email'].strip().lower()
        lozinka = request.form.get('lozinka', '').strip()
        uloga = request.form['uloga']
        razred_id = request.form.get('razred_id') or None
        if razred_id:
            razred_id = int(razred_id)

        if not ime or not email:
            flash('Ime i email su obavezni.', 'danger')
        else:
            try:
                if lozinka:
                    hashed = generate_password_hash(lozinka)
                    execute(
                        f'UPDATE korisnici SET ime={ph}, email={ph}, lozinka={ph}, uloga={ph}, razred_id={ph} WHERE id={ph}',
                        (ime, email, hashed, uloga, razred_id, id))
                else:
                    execute(
                        f'UPDATE korisnici SET ime={ph}, email={ph}, uloga={ph}, razred_id={ph} WHERE id={ph}',
                        (ime, email, uloga, razred_id, id))
                commit()
                flash('Korisnik je uspješno ažuriran.', 'success')
                return redirect(url_for('korisnici'))
            except Exception as e:
                flash(f'Greška pri ažuriranju. ({e})', 'danger')

    return render_template('korisnik_forma.html', korisnik=korisnik, razredi=razredi, akcija='uredi')


@app.route('/korisnici/brisi/<int:id>', methods=['POST'])
@admin_required
def brisi_korisnik(id):
    ph = '%s' if USE_POSTGRES else '?'
    if id == session['korisnik_id']:
        flash('Ne možete obrisati vlastiti račun.', 'danger')
        return redirect(url_for('korisnici'))
    execute(f'DELETE FROM korisnici WHERE id={ph}', (id,))
    commit()
    flash('Korisnik je obrisan.', 'success')
    return redirect(url_for('korisnici'))


@app.route('/nova-skolska-godina', methods=['POST'])
@admin_required
def nova_skolska_godina():
    ph = '%s' if USE_POSTGRES else '?'
    tekuca = _tekuca_godina()

    # Parse current year e.g. "2025/2026" -> next "2026/2027"
    parts = tekuca.split('/')
    try:
        god1 = int(parts[0])
        god2 = int(parts[1])
    except (ValueError, IndexError):
        flash('Neispravni format školske godine.', 'danger')
        return redirect(url_for('korisnici'))
    nova_godina = f'{god2}/{god2 + 1}'

    # Create 24 new razredi for the new year
    new_razred_ids = {}
    for r in range(1, 9):
        for o in ['A', 'B', 'C']:
            rid = lastrowid(
                f'INSERT INTO razredi (naziv, razina, skolska_godina) VALUES ({ph},{ph},{ph})',
                (f'{r}.{o}', r, nova_godina))
            new_razred_ids[(r, o)] = rid

    # Update razrednici assignments
    razrednici = query(
        f'SELECT k.id, k.razred_id, rz.razina, rz.naziv FROM korisnici k '
        f'JOIN razredi rz ON k.razred_id=rz.id '
        f'WHERE k.uloga={ph} AND k.razred_id IS NOT NULL',
        ('razrednik',))

    for r in razrednici:
        razina = r['razina']
        naziv = r['naziv']
        # Extract suffix: "1.A" -> "A"
        suffix = naziv.split('.')[-1].strip() if '.' in naziv else naziv[-1]

        if razina < 8:
            novi_razred_id = new_razred_ids.get((razina + 1, suffix))
            execute(
                f'UPDATE korisnici SET razred_id={ph} WHERE id={ph}',
                (novi_razred_id, r['id']))
        else:
            execute(
                f'UPDATE korisnici SET razred_id=NULL WHERE id={ph}',
                (r['id'],))

    commit()
    flash(f'Nova školska godina {nova_godina} je uspješno kreirana.', 'success')
    return redirect(url_for('korisnici'))


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
