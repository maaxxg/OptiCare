# Domenski sadržaj (E13-T1 do T3)

Sintetički nacrt koji treba pregledati član tima s poznavanjem domene. Sve je izmišljeno: imena, MBO i telefoni su očito lažni, nema ulica, a vrijednosti su procjene, ne klinički ni pravni podaci. Spornim vrijednostima u datotekama dodana je oznaka `# REVIEW:`.

## Datoteke

| Datoteka | Sadržaj | Koristi |
| --- | --- | --- |
| `patient_profiles.yaml` | 18 izmišljenih pacijenata s jednim zahtjevom za pregled | E1-T3 (početni podaci za demo) |
| `lika_line.yaml` | nekoliko linija Lika Line kao opcija javnog prijevoza (trasa i polasci) | E1-T3; kasnije planer i prijedlog putnog naloga |
| `urgency_and_durations.yaml` | djelatnosti, vrste pregleda, klase hitnosti, trajanje pregleda (medijan i 90. percentil), vrijeme ukrcaja | E1-T2 (šifrarnici), E4-T2 (zadana pravila) |
| `scoring_factors.yaml` | faktori bodovanja, težine, pojasevi i razine usluge | E3-T1 (bodovi potrebe za podrškom) |
| `synthetic_trips.yaml` | parametri raspodjela za generator povijesnih vožnji (`TripLog`) | E1-T4 (generator sintetičkih vožnji) |

## Načela

- Bodovi i razine samo dodaju pomoć. Nijedan faktor, prag ni razina ne smije ukloniti ili zapostaviti pacijenta.
- `expected_transport_entitlement` je očekivani prijedlog sustava, ne činjenica. Pravo utvrđuje izabrani liječnik.
- Popis djelatnosti vrijedi za sve ustanove. OB Gospić ima sve navedene djelatnosti osim onkologije, pa onkološki pregledi idu u KBC (`p08`, `p16` u KBC Rijeka).
- Pokretni pacijenti bez prava ne idu na sanitetska vozila. Oznaka `social_order_today: true` označava one koji bi danas vjerojatno dobili nalog iz socijalnih razloga.
- Pacijenti-vozači (`p05`, `p07`, `p15`) i potencijalni suputnici imaju `carpool_consent: true`. Vozač se uključuje u plan tek kad sestra potvrdi njegove dokumente (`driver_documents_confirmed`).
- Linije Lika Line nisu vozila: autobus vozi fiksnom trasom po voznom redu i planer ga ne raspoređuje.

## Otvorene stavke za pregled

- Heuristika prava na prijevoz u profilima (sanitetski za kolica i nosila, putni nalog izvan mjesta prebivališta). Odlučiti o graničnim slučajevima: pokretni pacijent na dijalizi (`p04`), pacijent sa štapom na dugoj relaciji (`p10`) i pacijentica sa štapom na trećem katu bez lifta (`p18`).
- Koja se zagrebačka bolnica koristi kao odredište (`kbc_zagreb` je nagađanje).
- Linije, stanice i polasci Lika Line u `lika_line.yaml` su nacrt; provjeriti stvarni vozni red.
- Gornje granice pomaka za klase hitnosti (3 i 30 dana).
- Trajanja pregleda (medijan i 90. percentil) za sve kombinacije, osobito dijalizu i onkološke postupke.
- Vremena ukrcaja po klasi pokretljivosti.
- Težine faktora bodovanja i njihov zbroj (1,0), pojasevi (udaljenost, dob, propušteni pregledi), vrijednosti za vrstu telefona i klasu pokretljivosti.
- Preklapanje faktora "Dostupnost pratnje" i "Živi sam" (dvostruko brojanje).
- Pragovi razina usluge (0,35 i 0,60) i pomoć koju dodaje svaka razina.
