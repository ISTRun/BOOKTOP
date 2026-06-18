# BOOKTOP — Fond knjiga školske knjižnice

Web aplikacija za praćenje fonda knjiga i izračun narudžbe na kraju školske godine.

## Pokretanje

```bash
pip install -r requirements.txt
python app.py
```

Aplikacija se pokreće na `http://0.0.0.0:5000` i dostupna je svim uređajima na lokalnoj mreži.

## Početni korisnici

| Uloga | Email | Lozinka |
|-------|-------|---------|
| Administrator | admin@skola.hr | admin123 |
| Razrednik 1.A | razrednik1a@skola.hr | razrednik123 |
| Razrednik 1.B | razrednik1b@skola.hr | razrednik123 |
| … (svaki razred ima svog razrednika) | | |

## Formula

```
X = N − (V + O)   (min 0)
```

- **V** = vraćene knjige (zbroj svih odjeljenja iste razine)
- **O** = rezerva iz prošlih godina
- **N** = broj upisanih učenika za sljedeću godinu
- **X** = broj knjiga za naručiti

## Razredi

Razredi 1–8, svaki s odjeljenjima A, B i C (ukupno 24 razreda).
