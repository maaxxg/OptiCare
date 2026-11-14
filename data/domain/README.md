# Domenski sadržaj (E13-T1 do T5)

Sintetički nacrt koji treba pregledati član tima s poznavanjem domene. Sve je izmišljeno: imena, MBO i telefoni su očito lažni, nema ulica, a vrijednosti su procjene, ne klinički ni pravni podaci. Oznake u datotekama:

- `PROCJENA (nije pronađen dobar izvor)`: vrijednost je razumna procjena; javni izvor nije pronađen (stanje 14. 11. 2026.). Ispraviti kad se dobije bolji podatak (bolnica, sanitetski vozač, HZZO).
- Vrijednosti s izvorom navode ga u komentaru (zakon, pravilnik, DZS, likaline.hr).

## Datoteke

| Datoteka | Sadržaj | Koristi |
| --- | --- | --- |
| `patient_profiles.yaml` | 18 izmišljenih pacijenata s jednim zahtjevom za pregled | E1-T3 (početni podaci za demo) |
| `lika_line.yaml` | nekoliko linija Lika Line kao opcija javnog prijevoza (trasa i polasci) | E1-T3; kasnije planer i prijedlog putnog naloga |
| `urgency_and_durations.yaml` | djelatnosti, vrste pregleda, klase hitnosti, trajanje pregleda (medijan i 90. percentil), vrijeme ukrcaja | E1-T2 (šifrarnici), E4-T2 (zadana pravila) |
| `scoring_factors.yaml` | faktori bodovanja, težine, pojasevi i razine usluge | E3-T1 (bodovi potrebe za podrškom) |
| `synthetic_trips.yaml` | parametri raspodjela za generator povijesnih vožnji (`TripLog`); `python -m app.seed` ga uvijek pokreće | E1-T4 (generator sintetičkih vožnji) |
| `hzzo_rules.yaml` | pravila HZZO-a: sanitetski prijevoz, putni nalog (prag 50 km, iznimke), tko izdaje nalog, izvori | E3-T2 (provjera prava na prijevoz) |
| `extraction_examples.yaml` | 34 rečenice pacijenata (iz poziva) s očekivanim izdvojenim poljima, uključujući primjere s MBO-om i s podacima koji nedostaju | E2-T4 (točnost izdvajanja po polju, usporedba veličina Qwena) |

## Načela

- Bodovi i razine samo dodaju pomoć. Nijedan faktor, prag ni razina ne smije ukloniti ili zapostaviti pacijenta.
- `expected_transport_entitlement` je očekivani prijedlog sustava, ne činjenica. Pravo utvrđuje izabrani liječnik.
- Popis djelatnosti vrijedi za sve ustanove. OB Gospić ima sve navedene djelatnosti osim onkologije, pa onkološki pregledi idu u KBC (`p08`, `p16` u KBC Rijeka).
- Pokretni pacijenti bez prava ne idu na sanitetska vozila. Oznaka `social_order_today: true` označava one koji bi danas vjerojatno dobili nalog iz socijalnih razloga.
- Pacijenti-vozači (`p05`, `p07`, `p15`) i potencijalni suputnici imaju `carpool_consent: true`. Vozač se uključuje u plan tek kad sestra potvrdi njegove dokumente (`driver_documents_confirmed`).
- Linije Lika Line nisu vozila: autobus vozi fiksnom trasom po voznom redu i planer ga ne raspoređuje.

## Napomene

- Pravo na prijevoz u profilima slijedi `hzzo_rules.yaml`. Pacijenti sa štapom (`p01`, `p04`, `p10`, `p18`) dobivaju prijedlog bez saniteta i oznaku da liječnik procijeni pravo na sanitet. Rubne udaljenosti oko 50 km (`p01`, `p14`, `p15`) treba provjeriti na HAK karti. Za `p07` i `p10` odredište nije najbliža ustanova s tom djelatnošću.
- Linije i polasci Lika Line u `lika_line.yaml` prepisani su sa službenog voznog reda (likaline.hr, 14. 11. 2026.); prije prikaza korisniku provjeriti jesu li još aktualni.
- Oznake `review` u `extraction_examples.yaml` su dio očekivanog izlaza (izdvajanje ih mora označiti sestri), ne otvorena pitanja. Pravila za dob iz rednog broja, štake, auto koji se ne smije voziti i propuštene preglede bez vremenskog okvira opisana su u zaglavlju datoteke; dio dana ima šifrarnik `times_of_day`.

## Odluke tima (14. 11. 2026.)

- Kemoterapija i radioterapija su zasebne vrste pregleda (`chemotherapy`, `radiotherapy`); iz njih provjera prava (E3-T2) zna da vrijedi iznimka za putni nalog. Onkološka obrada ostaje `procedure_test`.
- `p10` ide na subspecijalistički neurološki pregled u KBC Rijeka (najbliži KBC), uz ručnu oznaku sestre da bliže nema te djelatnosti.
- "Živi sam" i "Dostupnost pratnje" ostaju odvojeni faktori: prvi je pomoć kod kuće, drugi pratnja na pregled.
- Pacijent na nosilima uvijek dobiva barem visoku razinu usluge (`min_level_by_mobility`).
