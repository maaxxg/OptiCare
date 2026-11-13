# Primjeri profila pacijenata za demo (E1-T3 / E13-T1)

Ovaj dokument sadrži **18 raznolikih profila pacijenata (`p01`–`p18`)** iz svih dijelova Ličko-senjske županije koji pokrivaju:
- sve klase pokretljivosti (`walks`, `cane`, `wheelchair`, `stretcher`),
- sve djelatnosti (`internal_medicine`, `cardiology`, `ophthalmology`, `orthopaedics`, `neurology`, `radiology`, `oncology`, `dialysis`),
- sve vrste pregleda (`first_visit`, `follow_up`, `procedure_test`, `dialysis_session`) i klase hitnosti (`fixed`, `within_few_days`, `within_week`, `within_month`),
- tri odredišta (`ob_gospic`, `kbc_rijeka`, `kbc_zagreb`),
- pacijente-vozače s vlastitim autom (`p05`, `p07`, `p15`),
- pokretne pacijente bez prijevoza koji bi danas dobili nalog za sanitetski prijevoz iz socijalnih razloga (`social_order_today: true`: `p06`, `p08`, `p09`, `p11`, `p14`, `p17`).

---

### Pacijent p01

```yaml
key: p01
first_name: Marija
last_name: Marijević
birth_year: 1951                             # npr. 1945
mbo: "096869695"                             # točno 9 znamenki (npr. "000000001" do "000000020")
phone: "+385 98 537 775"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
# Općine/gradovi: Gospić | Otočac | Senj | Novalja | Plitvička Jezera | Perušić | Udbina | Brinje | Karlobag | Vrhovine | Donji Lapac | Lovinac
# Primjeri naselja: Gospić, Smiljan, Lički Osik | Otočac, Kuterevo | Senj, Jablanac | Novalja, Metajna | Korenica | Perušić, Kosinj | Udbina | Brinje | Karlobag | Vrhovine
settlement: Udbina
municipality: Udbina
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: cane                         # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 1                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: false                    # true | false  (true = pokretan pacijent koji bi danas dobio sanitetski iz socijalnih razloga)
own_car: false                               # true | false  (true = pacijent-vozač)
carpool_driver_seats: 0                      # 0 (ako nema auto) | 1 | 2 | 3 (slobodna mjesta ako je own_car: true)
carpool_consent: true                        # true | false  (pristaje li voziti druge ili voziti se sa sumještaninom)

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 4                   # cijeli broj >= 0 (npr. 0, 1, 2, 3)
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: ophthalmology                  # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: procedure_test                 # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_month                # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 30                     # mora biti <= max pomaka za urgency_class (1 za fixed, <=3 za within_few_days, <=7 za within_week, <=30 za within_month)
  recurrence: null                           # null | "3x_weekly" (npr. za dijalizu)

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Dioptrija mi više ne paše, trebam nove naočale. Nemam način za doći do bolnice, ali mi nije problem ići s nepoznatom osobom."
```

---

### Pacijent p02

```yaml
key: p02
first_name: Ivan
last_name: Kovačević
birth_year: 1958                             # npr. 1945
mbo: "102938475"                             # točno 9 znamenki
phone: "+385 91 224 8810"
phone_type: basic_mobile                     # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Otočac
municipality: Otočac
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: wheelchair                   # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: sanitetski   # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: orthopaedics                   # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 5                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "U invalidskim sam kolicima nakon operacije kuka i trebam kontrolu kod ortopeda u Gospiću. Supruga ide sa mnom kao pratnja."
```

---

### Pacijent p03

```yaml
key: p03
first_name: Ana
last_name: Babić
birth_year: 1936                             # npr. 1945
mbo: "293847561"                             # točno 9 znamenki
phone: "+385 53 771 204"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Senj
municipality: Senj
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: stretcher                    # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 1                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: sanitetski   # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: radiology                      # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: procedure_test                 # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_few_days             # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 3                      # <= 3 za within_few_days
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Majka je nepokretna i leži u krevetu na prvom katu bez lifta, a mora na hitno CT snimanje u Gospić. Ja živim s njom i idem u pratnju."
```

---

### Pacijent p04

```yaml
key: p04
first_name: Josip
last_name: Marić
birth_year: 1962                             # npr. 1945
mbo: "384756192"                             # točno 9 znamenki
phone: "+385 92 311 4509"
phone_type: basic_mobile                     # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Korenica
municipality: Plitvička Jezera
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: cane                         # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: sanitetski   # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: dialysis                       # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: dialysis_session               # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: fixed                       # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 1                      # točno 1 za fixed
  recurrence: "3x_weekly"                    # null | "3x_weekly" (npr. za dijalizu)

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Idem redovito tri puta tjedno na dijalizu u Gospić i termin se ne smije pomicati. Hodam uz štap, a nakon dijalize sam previše iscrpljen za samostalan put."
```

---

### Pacijent p05

```yaml
key: p05
first_name: Stjepan
last_name: Perković
birth_year: 1955                             # npr. 1945
mbo: "475869102"                             # točno 9 znamenki
phone: "+385 98 441 920"
phone_type: smartphone                       # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Perušić
municipality: Perušić
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: none         # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: true                                # true | false  (pacijent-vozač #1)
carpool_driver_seats: 3                      # 3 slobodna mjesta u autu
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: true              # true | false
driver_insurance_valid: true                 # true | false
driver_license_valid: true                   # true | false
volunteer_partner: "Crveni križ Gospić"      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: ophthalmology                  # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 1                      # ide sutra svojim autom
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Sutra idem svojim autom iz Perušića u Gospić na kontrolu očnog tlaka. Imam tri slobodna mjesta i rado ću povesti susjede iz općine koji idu u bolnicu."
```

---

### Pacijent p06

```yaml
key: p06
first_name: Katica
last_name: Starčević
birth_year: 1949                             # npr. 1945
mbo: "586970213"                             # točno 9 znamenki
phone: "+385 91 605 3321"
phone_type: basic_mobile                     # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Kosinj
municipality: Perušić
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: true                     # pokretna, ali bez javnog prijevoza iz Kosinja
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # pristaje na vožnju sa sumještaninom (npr. p05)

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 2                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: internal_medicine              # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 4                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sama u Kosinju i mogu hodati, ali iz sela nema autobusa u vrijeme pregleda. Rado bih išla s nekim iz Perušića ako ide prema bolnici u Gospiću."
```

---

### Pacijent p07

```yaml
key: p07
first_name: Ante
last_name: Rukavina
birth_year: 1953                             # npr. 1945
mbo: "697081324"                             # točno 9 znamenki
phone: "+385 99 712 4401"
phone_type: smartphone                       # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Otočac
municipality: Otočac
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: none         # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: true                                # true | false  (pacijent-vozač #2, ide u Rijeku)
carpool_driver_seats: 2                      # 2 slobodna mjesta
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: true              # true | false
driver_insurance_valid: true                 # true | false
driver_license_valid: true                   # true | false
volunteer_partner: "Crveni križ Gospić"      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: kbc_rijeka                    # ob_gospic | kbc_rijeka | kbc_zagreb
  department: cardiology                     # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: procedure_test                 # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 1                      # ide sutra u Rijeku
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Imam naručen ultrazvuk srca u KBC-u Rijeka i vozim vlastitim autom preko Senja. Mogu usput povesti dvoje ljudi koji taj dan idu za Rijeku."
```

---

### Pacijent p08

```yaml
key: p08
first_name: Jelena
last_name: Žugaj
birth_year: 1952                             # npr. 1945
mbo: "708192435"                             # točno 9 znamenki
phone: "+385 95 883 1102"
phone_type: basic_mobile                     # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Senj
municipality: Senj
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 1                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: true                     # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # pristaje na zajedničku vožnju za Rijeku

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 1                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: kbc_rijeka                    # ob_gospic | kbc_rijeka | kbc_zagreb
  department: oncology                       # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 3                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sama u Senju i samostalno hodam, a moram na onkološku kontrolu u Rijeku. Autobusna linija mi ne odgovara pa bih rado išla organiziranim ili zajedničkim prijevozom."
```

---

### Pacijent p09

```yaml
key: p09
first_name: Mirko
last_name: Devčić
birth_year: 1947                             # npr. 1945
mbo: "819203546"                             # točno 9 znamenki
phone: "+385 53 562 918"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Smiljan
municipality: Gospić
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: none         # unutar istog grada/općine (Gospić), pokretan
social_order_today: true                     # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 1                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: cardiology                     # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: first_visit                    # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 5                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sam u Smiljanu, dobro hodam i trebam prvi pregled kod kardiologa u Gospiću. Sin radi u Zagrebu pa me nema tko odvesti."
```

---

### Pacijent p10

```yaml
key: p10
first_name: Nikola
last_name: Vukelić
birth_year: 1950                             # npr. 1945
mbo: "920314657"                             # točno 9 znamenki
phone: "+385 91 510 7782"
phone_type: basic_mobile                     # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Novalja
municipality: Novalja
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: cane                         # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 1                                     # cijeli broj (0 = prizemlje / kuća)
elevator: true                               # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: kbc_zagreb                    # ob_gospic | kbc_rijeka | kbc_zagreb
  department: neurology                      # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: first_visit                    # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_month                # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 14                     # <= 30 za within_month
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Iz Novalje sam i upućen sam na prvi subspecijalistički neurološki pregled u KBC Zagreb. Hodam uz štap, a supruga ide sa mnom kao pratnja."
```

---

### Pacijent p11

```yaml
key: p11
first_name: Dragica
last_name: Pavlić
birth_year: 1944                             # npr. 1945
mbo: "135792468"                             # točno 9 znamenki
phone: "+385 53 688 112"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Donji Lapac
municipality: Donji Lapac
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: true                     # daleko od Gospića, bez javne linije
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 2                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: internal_medicine              # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: first_visit                    # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 4                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sama u Donjem Lapcu i hodam bez pomagala, ali sam već dvaput propustila pregled jer nisam imala čime doći do Gospića."
```

---

### Pacijent p12

```yaml
key: p12
first_name: Mate
last_name: Bogdan
birth_year: 1969                             # npr. 1945
mbo: "246813579"                             # točno 9 znamenki
phone: "+385 98 901 2345"
phone_type: smartphone                       # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Brinje
municipality: Brinje
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: radiology                      # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: procedure_test                 # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 6                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Iz Brinja sam i trebam ultrazvuk abdomena u Gospiću. Pokretan sam i koristim pametni telefon, ali mi je auto u kvaru pa trebam prijevoz."
```

---

### Pacijent p13

```yaml
key: p13
first_name: Ljubica
last_name: Tomljenović
birth_year: 1938                             # npr. 1945
mbo: "369258147"                             # točno 9 znamenki
phone: "+385 53 694 033"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Karlobag
municipality: Karlobag
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: wheelchair                   # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: sanitetski   # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: orthopaedics                   # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: first_visit                    # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_month                # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 20                     # <= 30 za within_month
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "U invalidskim sam kolicima i živim s kćeri u Karlobagu. Trebam prvi pregled kod ortopeda u Gospiću i vozilo s mjestom za kolica."
```

---

### Pacijent p14

```yaml
key: p14
first_name: Zdravko
last_name: Mesić
birth_year: 1951                             # npr. 1945
mbo: "741852963"                             # točno 9 znamenki
phone: "+385 53 775 190"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Vrhovine
municipality: Vrhovine
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: true                     # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 1                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: neurology                      # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 4                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sam u Vrhovinama, hodam samostalno, ali nemam auto ni prijevoz do Gospića za neurološku kontrolu."
```

---

### Pacijent p15

```yaml
key: p15
first_name: Damir
last_name: Blažević
birth_year: 1960                             # npr. 1945
mbo: "852963741"                             # točno 9 znamenki
phone: "+385 99 340 1188"
phone_type: smartphone                       # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Udbina
municipality: Udbina
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: none         # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: true                                # true | false  (pacijent-vozač #3 iz Udbine)
carpool_driver_seats: 2                      # 2 slobodna mjesta
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: true              # true | false
driver_insurance_valid: true                 # true | false
driver_license_valid: true                   # true | false
volunteer_partner: "Crveni križ Gospić"      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: cardiology                     # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 2                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Idem vlastitim autom iz Udbine na kardiološku kontrolu u Gospić. Imam dva slobodna mjesta pa mogu povesti susjede iz Udbine koji trebaju u bolnicu."
```

---

### Pacijent p16

```yaml
key: p16
first_name: Petar
last_name: Ivezić
birth_year: 1973                             # npr. 1945
mbo: "963852741"                             # točno 9 znamenki
phone: "+385 98 715 6604"
phone_type: smartphone                       # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Kuterevo
municipality: Otočac
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: false                           # true | false
companion: true                              # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 0                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: oncology                       # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: procedure_test                 # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_few_days             # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 3                      # <= 3 za within_few_days
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Iz Kutereva sam i moram u roku od par dana na onkološku obradu u Gospić. Pokretan sam i supruga ide sa mnom, ali nemamo automobil."
```

---

### Pacijent p17

```yaml
key: p17
first_name: Danica
last_name: Šarić
birth_year: 1942                             # npr. 1945
mbo: "159487263"                             # točno 9 znamenki
phone: "+385 91 490 8821"
phone_type: basic_mobile                     # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Lovinac
municipality: Lovinac
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: walks                        # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 0                                     # cijeli broj (0 = prizemlje / kuća)
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: travel_order # sanitetski | travel_order | none
social_order_today: true                     # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: true                        # true | false

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 2                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: ophthalmology                  # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: follow_up                      # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_month                # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 10                     # <= 30 za within_month
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sama u Lovincu i hodam samostalno, a trebam oftalmološku kontrolu u Gospiću. Dosad su mi pisali nalog za sanitet jer nemam čime doći."
```

---

### Pacijent p18

```yaml
key: p18
first_name: Milka
last_name: Rončević
birth_year: 1940                             # npr. 1945
mbo: "753951486"                             # točno 9 znamenki
phone: "+385 53 572 809"
phone_type: landline                         # landline | basic_mobile | smartphone

# Lokacija (Ličko-senjska županija)
settlement: Gospić
municipality: Gospić
county: Ličko-senjska

# Pokretljivost i kućanstvo
mobility_class: cane                         # walks | cane | wheelchair | stretcher
lives_alone: true                            # true | false
companion: false                             # true | false  (ima li pratnju)
floor: 3                                     # treći kat bez lifta -> visoka potreba za podrškom
elevator: false                              # true | false

# Pravo na prijevoz i zajednička vožnja (carpool)
expected_transport_entitlement: none         # unutar mjesta prebivališta, hoda uz štap
social_order_today: false                    # true | false
own_car: false                               # true | false
carpool_driver_seats: 0                      # 0 | 1 | 2 | 3
carpool_consent: false                       # treba pomoć vozača od vrata do vrata (kat bez lifta)

# Samo ako je own_car: true (pacijent-vozač), inače ostavi false / null:
driver_registration_valid: false             # true | false
driver_insurance_valid: false                # true | false
driver_license_valid: false                  # true | false
volunteer_partner: null                      # null | "Crveni križ Gospić"

# Povijest i privola
missed_visits_last_year: 3                   # cijeli broj >= 0
consent_given: true                          # true | false

# Zahtjev za pregled
visit:
  destination: ob_gospic                     # ob_gospic | kbc_rijeka | kbc_zagreb
  department: neurology                      # internal_medicine | cardiology | ophthalmology | orthopaedics | neurology | radiology | oncology | dialysis
  visit_type: procedure_test                 # first_visit | follow_up | procedure_test | dialysis_session
  urgency_class: within_week                 # fixed (0 dana) | within_few_days (<=3 dana) | within_week (<=7 dana) | within_month (<=30 dana)
  earliest_offset_days: 1                    # dani od danas (1 = sutra)
  latest_offset_days: 4                      # <= 7 za within_week
  recurrence: null                           # null | "3x_weekly"

# Kratka priča / što pacijent ili sestra kaže u pozivu (1-2 rečenice)
story: "Živim sama u Gospiću na trećem katu bez lifta i teško silazim niz stepenice sa štapom. Već sam triput propustila EMNG pretragu jer mi nema tko pomoći do vozila."
```
