import sqlite3
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'booktop-secret-2024')

DATABASE = 'booktop.db'


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE IF NOT EXISTS korisnici (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ime TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            lozinka TEXT NOT NULL,
            uloga TEXT NOT NULL CHECK(uloga IN ('razrednik', 'administrator')),
            razred_id INTEGER REFERENCES razredi(id)
        );

        CREATE TABLE IF NOT EXISTS razredi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naziv TEXT NOT NULL,
            razina INTEGER NOT NULL,
            skolska_godina TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS predmeti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            naziv TEXT NOT NULL,
            razina INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS vraceno (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razred_id INTEGER NOT NULL REFERENCES razredi(id),
            predmet_id INTEGER NOT NULL REFERENCES predmeti(id),
            kolicina INTEGER NOT NULL DEFAULT 0,
            skolska_godina TEXT NOT NULL,
            korisnik_id INTEGER REFERENCES korisnici(id),
            datum TEXT DEFAULT (date('now')),
            UNIQUE(razred_id, predmet_id, skolska_godina)
        );

        CREATE TABLE IF NOT EXISTS rezerva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razina INTEGER NOT NULL,
            predmet_id INTEGER NOT NULL REFERENCES predmeti(id),
            kolicina INTEGER NOT NULL DEFAULT 0,
            skolska_godina TEXT NOT NULL,
            UNIQUE(razina, predmet_id, skolska_godina)
        );

        CREATE TABLE IF NOT EXISTS upisi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            razina INTEGER NOT NULL,
            broj_ucenika INTEGER NOT NULL DEFAULT 0,
            skolska_godina TEXT NOT NULL,
            UNIQUE(razina, skolska_godina)
        );
    ''')
    db.commit()
    _seed_data(db)
    db.close()


def _seed_data(db):
    from werkzeug.security import generate_password_hash

    existing = db.execute('SELECT COUNT(*) as c FROM korisnici').fetchone()['c']
    if existing > 0:
        return

    godina = '2025/2026'
    razine = list(range(1, 9))
    odjeljenja = ['A', 'B', 'C']

    razred_ids = {}
    for r in razine:
        for o in odjeljenja:
            naziv = f'{r}.{o}'
            cur = db.execute(
                'INSERT INTO razredi (naziv, razina, skolska_godina) VALUES (?, ?, ?)',
                (naziv, r, godina)
            )
            razred_ids[(r, o)] = cur.lastrowid

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
                cur = db.execute(
                    'INSERT INTO predmeti (naziv, razina) VALUES (?, ?)',
                    (naziv, razina)
                )
                predmet_ids[key] = cur.lastrowid

    admin_pass = generate_password_hash('admin123')
    db.execute(
        'INSERT INTO korisnici (ime, email, lozinka, uloga) VALUES (?, ?, ?, ?)',
        ('Knjižničarka', 'admin@skola.hr', admin_pass, 'administrator')
    )

    razrednik_data = [
        ('Marija Kovač', 'razrednik1a@skola.hr', (1, 'A')),
        ('Ivan Horvat', 'razrednik1b@skola.hr', (1, 'B')),
        ('Ana Perić', 'razrednik1c@skola.hr', (1, 'C')),
        ('Petra Novak', 'razrednik2a@skola.hr', (2, 'A')),
        ('Josip Babić', 'razrednik2b@skola.hr', (2, 'B')),
        ('Lucija Tomić', 'razrednik2c@skola.hr', (2, 'C')),
        ('Tomislav Jurić', 'razrednik3a@skola.hr', (3, 'A')),
        ('Sandra Marić', 'razrednik3b@skola.hr', (3, 'B')),
        ('Damir Vidović', 'razrednik3c@skola.hr', (3, 'C')),
        ('Vesna Blažić', 'razrednik4a@skola.hr', (4, 'A')),
        ('Nikola Pavić', 'razrednik4b@skola.hr', (4, 'B')),
        ('Kristina Vuković', 'razrednik4c@skola.hr', (4, 'C')),
        ('Mario Filipović', 'razrednik5a@skola.hr', (5, 'A')),
        ('Đurđica Knežević', 'razrednik5b@skola.hr', (5, 'B')),
        ('Stjepan Majić', 'razrednik5c@skola.hr', (5, 'C')),
        ('Mirela Lončar', 'razrednik6a@skola.hr', (6, 'A')),
        ('Dragan Šimić', 'razrednik6b@skola.hr', (6, 'B')),
        ('Renata Bogdanović', 'razrednik6c@skola.hr', (6, 'C')),
        ('Zlatko Đukić', 'razrednik7a@skola.hr', (7, 'A')),
        ('Helena Miletić', 'razrednik7b@skola.hr', (7, 'B')),
        ('Krešimir Rukavina', 'razrednik7c@skola.hr', (7, 'C')),
        ('Dijana Galić', 'razrednik8a@skola.hr', (8, 'A')),
        ('Boris Živković', 'razrednik8b@skola.hr', (8, 'B')),
        ('Tatjana Radić', 'razrednik8c@skola.hr', (8, 'C')),
    ]

    lozinka = generate_password_hash('razrednik123')
    for ime, email, (razina, odjeljenje) in razrednik_data:
        rid = razred_ids[(razina, odjeljenje)]
        db.execute(
            'INSERT INTO korisnici (ime, email, lozinka, uloga, razred_id) VALUES (?, ?, ?, ?, ?)',
            (ime, email, lozinka, 'razrednik', rid)
        )

    db.commit()


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
        db = get_db()
        korisnik = db.execute(
            'SELECT * FROM korisnici WHERE LOWER(email) = ?', (email,)
        ).fetchone()
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

    db = get_db()
    razred_id = session['razred_id']
    razred = db.execute('SELECT * FROM razredi WHERE id = ?', (razred_id,)).fetchone()
    if not razred:
        flash('Razred nije pronađen.', 'danger')
        return redirect(url_for('logout'))

    godina = razred['skolska_godina']
    predmeti = db.execute(
        'SELECT * FROM predmeti WHERE razina = ? ORDER BY naziv', (razred['razina'],)
    ).fetchall()

    if request.method == 'POST':
        for predmet in predmeti:
            kolicina = int(request.form.get(f'v_{predmet["id"]}', 0) or 0)
            db.execute('''
                INSERT INTO vraceno (razred_id, predmet_id, kolicina, skolska_godina, korisnik_id, datum)
                VALUES (?, ?, ?, ?, ?, date('now'))
                ON CONFLICT(razred_id, predmet_id, skolska_godina)
                DO UPDATE SET kolicina = excluded.kolicina,
                              korisnik_id = excluded.korisnik_id,
                              datum = excluded.datum
            ''', (razred_id, predmet['id'], kolicina, godina, session['korisnik_id']))
        db.commit()
        flash('Podaci su uspješno spremljeni.', 'success')
        return redirect(url_for('moj_razred'))

    vraceno_map = {}
    for row in db.execute(
        'SELECT predmet_id, kolicina FROM vraceno WHERE razred_id = ? AND skolska_godina = ?',
        (razred_id, godina)
    ).fetchall():
        vraceno_map[row['predmet_id']] = row['kolicina']

    return render_template('moj_razred.html', razred=razred, predmeti=predmeti,
                           vraceno_map=vraceno_map, godina=godina)


@app.route('/rezerva', methods=['GET', 'POST'])
@admin_required
def rezerva():
    db = get_db()
    razine = list(range(1, 9))
    godina = _tekuca_godina(db)

    if request.method == 'POST':
        for razina in razine:
            predmeti = db.execute(
                'SELECT * FROM predmeti WHERE razina = ?', (razina,)
            ).fetchall()
            for predmet in predmeti:
                kolicina = int(request.form.get(f'o_{razina}_{predmet["id"]}', 0) or 0)
                db.execute('''
                    INSERT INTO rezerva (razina, predmet_id, kolicina, skolska_godina)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(razina, predmet_id, skolska_godina)
                    DO UPDATE SET kolicina = excluded.kolicina
                ''', (razina, predmet['id'], kolicina, godina))
        db.commit()
        flash('Rezerva je uspješno spremljena.', 'success')
        return redirect(url_for('rezerva'))

    data = {}
    for razina in razine:
        predmeti = db.execute(
            'SELECT * FROM predmeti WHERE razina = ? ORDER BY naziv', (razina,)
        ).fetchall()
        rezerve = {}
        for row in db.execute(
            'SELECT predmet_id, kolicina FROM rezerva WHERE razina = ? AND skolska_godina = ?',
            (razina, godina)
        ).fetchall():
            rezerve[row['predmet_id']] = row['kolicina']
        data[razina] = {'predmeti': predmeti, 'rezerve': rezerve}

    return render_template('rezerva.html', data=data, razine=razine, godina=godina)


@app.route('/upisi', methods=['GET', 'POST'])
@admin_required
def upisi():
    db = get_db()
    razine = list(range(1, 9))
    godina = _tekuca_godina(db)

    if request.method == 'POST':
        for razina in razine:
            broj = int(request.form.get(f'n_{razina}', 0) or 0)
            db.execute('''
                INSERT INTO upisi (razina, broj_ucenika, skolska_godina)
                VALUES (?, ?, ?)
                ON CONFLICT(razina, skolska_godina)
                DO UPDATE SET broj_ucenika = excluded.broj_ucenika
            ''', (razina, broj, godina))
        db.commit()
        flash('Broj upisanih učenika je uspješno spremljen.', 'success')
        return redirect(url_for('upisi'))

    upisi_map = {}
    for row in db.execute(
        'SELECT razina, broj_ucenika FROM upisi WHERE skolska_godina = ?', (godina,)
    ).fetchall():
        upisi_map[row['razina']] = row['broj_ucenika']

    return render_template('upisi.html', razine=razine, upisi_map=upisi_map, godina=godina)


@app.route('/izvjestaj')
@admin_required
def izvjestaj():
    db = get_db()
    godina = _tekuca_godina(db)
    razine = list(range(1, 9))

    upisi_map = {}
    for row in db.execute(
        'SELECT razina, broj_ucenika FROM upisi WHERE skolska_godina = ?', (godina,)
    ).fetchall():
        upisi_map[row['razina']] = row['broj_ucenika']

    rezerva_map = {}
    for row in db.execute(
        'SELECT razina, predmet_id, kolicina FROM rezerva WHERE skolska_godina = ?', (godina,)
    ).fetchall():
        rezerva_map[(row['razina'], row['predmet_id'])] = row['kolicina']

    vraceno_po_razini = {}
    for row in db.execute('''
        SELECT r.razina, v.predmet_id, SUM(v.kolicina) as ukupno
        FROM vraceno v
        JOIN razredi r ON v.razred_id = r.id
        WHERE v.skolska_godina = ?
        GROUP BY r.razina, v.predmet_id
    ''', (godina,)).fetchall():
        vraceno_po_razini[(row['razina'], row['predmet_id'])] = row['ukupno']

    izvjestaj_data = []
    narudzba = []

    for razina in razine:
        predmeti = db.execute(
            'SELECT * FROM predmeti WHERE razina = ? ORDER BY naziv', (razina,)
        ).fetchall()
        n = upisi_map.get(razina, 0)
        redovi = []
        for predmet in predmeti:
            v = vraceno_po_razini.get((razina, predmet['id']), 0)
            o = rezerva_map.get((razina, predmet['id']), 0)
            x = max(0, n - (v + o))
            redovi.append({
                'predmet': predmet['naziv'],
                'predmet_id': predmet['id'],
                'v': v, 'o': o, 'n': n, 'x': x
            })
            if x > 0:
                existing = next((item for item in narudzba if item['predmet_id'] == predmet['id'] and item['razina'] == razina), None)
                if not existing:
                    narudzba.append({'razina': razina, 'predmet': predmet['naziv'],
                                     'predmet_id': predmet['id'], 'x': x})
        izvjestaj_data.append({'razina': razina, 'n': n, 'redovi': redovi})

    return render_template('izvjestaj.html', izvjestaj_data=izvjestaj_data,
                           narudzba=narudzba, godina=godina)


@app.route('/korisnici')
@admin_required
def korisnici():
    db = get_db()
    svi = db.execute('''
        SELECT k.*, r.naziv as razred_naziv
        FROM korisnici k
        LEFT JOIN razredi r ON k.razred_id = r.id
        ORDER BY k.uloga, k.ime
    ''').fetchall()
    return render_template('korisnici.html', korisnici=svi)


def _tekuca_godina(db):
    row = db.execute('SELECT skolska_godina FROM razredi LIMIT 1').fetchone()
    return row['skolska_godina'] if row else '2025/2026'


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
