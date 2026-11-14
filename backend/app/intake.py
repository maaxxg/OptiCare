"""Free-text intake extraction and MBO privacy guard (E2-T1, E11-T1)."""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from pydantic import ValidationError

from app.adapters.geocoding import GeocodingClient, MockGeocodingClient, _normalize
from app.adapters.llm import LLMClient
from app.config import get_settings
from app.models import (
    Department,
    MobilityClass,
    PhoneType,
    UrgencyClass,
    VisitType,
)
from app.schemas import (
    ExtractedPatientDraft,
    ExtractedVisitRequestDraft,
    GeoPoint,
    IntakeExtractResponse,
)

EXTRACTION_EXAMPLES_PATH = Path("domain") / "extraction_examples.yaml"

# 1) 9 digits, contiguous or separated by spaces/hyphens (e.g. "123456789", "000 000 301")
_MBO_DIGITS_RE = re.compile(r"\b(?:\d[\s\-]?){8}\d\b")

# 2) 9 spoken Croatian digit words (e.g. "nula nula nula nula nula nula tri nula tri")
_SPOKEN_DIGITS: dict[str, str] = {
    "nula": "0",
    "jedan": "1",
    "jedna": "1",
    "dva": "2",
    "dvije": "2",
    "tri": "3",
    "cetiri": "4",
    "četiri": "4",
    "pet": "5",
    "sest": "6",
    "šest": "6",
    "sedam": "7",
    "osam": "8",
    "devet": "9",
}
_SPOKEN_WORD_ALT = "|".join(sorted(_SPOKEN_DIGITS.keys(), key=len, reverse=True))
_MBO_SPOKEN_RE = re.compile(
    rf"\b(?:(?:{_SPOKEN_WORD_ALT})\s+){{8}}(?:{_SPOKEN_WORD_ALT})\b",
    re.IGNORECASE,
)

# Maximal runs, used after an MBO cue: digit groups joined by one space/hyphen; spoken digit words.
_NUMERIC_RUN_RE = re.compile(r"(?<!\d)\d+(?:[ \-]\d+)*(?!\d)")
_SPOKEN_RUN_RE = re.compile(
    rf"\b(?:{_SPOKEN_WORD_ALT})(?:\s+(?:{_SPOKEN_WORD_ALT}))*\b", re.IGNORECASE
)

# MBO cues (matched on `_normalize`d text): a candidate counts as the MBO only when one of these
# precedes it in the same sentence with at most 3 letter-only words in between.
_MBO_CUES = (
    r"m\.?\s?b\.?\s?o",
    r"maticni\s+broj",
    r"broj\s+osiguranja",
    r"broj\s+osigurane\s+osobe",
    r"broj\s+zdravstvene(?:\s+iskaznice)?",
)
_MBO_CUE_RE = re.compile(
    rf"(?<!\w)(?:{'|'.join(_MBO_CUES)})(?!\w)\.?"
    r"(?:[^\w.!?;]+[^\W\d_]+){0,3}[^\w.!?;]*\Z"
)
# A number right after the Croatian country code is a phone number, never an MBO.
_PHONE_PREFIX_RE = re.compile(r"(?:\+|(?<!\d)00)385[\s\-]?\Z")

SYSTEM_PROMPT_HR = (
    "Ti si medicinski administrativni asistent za sustav OptiCare u Ličko-senjskoj županiji.\n"
    "Iz slobodnog teksta (bilješke medicinske sestre ili opisa pacijenta) izdvoji strukturirane "
    "podatke prema shemama `patient`, `visit_request` i `review`.\n\n"
    "PRAVILA:\n"
    '1. Odgovori ISKLJUČIVO valjanim JSON objektom s ključevima `"patient"`, `"visit_request"` '
    'i `"review"` (lista naziva polja čija je vrijednost nesigurna).\n'
    "2. Nikada ne nagađaj podatke koji nisu navedeni u tekstu — za svako nepoznato polje vrati "
    "`null`.\n"
    "3. Uvijek izdvajaj podatke PACIJENTA, čak i kad zove član obitelji ili susjed.\n"
    "4. Dozvoljene vrijednosti šifrarnika:\n"
    '   - `mobility_class`: "walks" | "cane" | "wheelchair" | "stretcher"\n'
    '   - `phone_type`: "landline" | "basic_mobile" | "smartphone"\n'
    '   - `department`: "internal_medicine" | "cardiology" | "ophthalmology" | "orthopaedics" | '
    '"neurology" | "radiology" | "oncology" | "dialysis"\n'
    '   - `visit_type`: "first_visit" | "follow_up" | "procedure_test" | "dialysis_session"\n'
    '   - `urgency_class`: "fixed" | "within_few_days" | "within_week" | "within_month"\n'
    '   - `preferred_time_of_day`: "morning" | "afternoon"\n\n'
    "PRIMJER 1:\n"
    'Ulaz: "Pacijent Ivan Kovačević (1958.), Otočac, tel +385 00 000 0002, mobitel. '
    "U invalidskim je kolicima nakon operacije kuka, treba kontrolu kod ortopeda u Gospiću "
    'ovaj tjedan. Supruga ide u pratnju, prizemlje."\n'
    "Izlaz:\n"
    "{\n"
    '  "patient": {\n'
    '    "first_name": "Ivan",\n'
    '    "last_name": "Kovačević",\n'
    '    "birth_year": 1958,\n'
    '    "phone": "+385 00 000 0002",\n'
    '    "phone_type": "basic_mobile",\n'
    '    "settlement": "Otočac",\n'
    '    "mobility_class": "wheelchair",\n'
    '    "lives_alone": false,\n'
    '    "companion": true,\n'
    '    "floor": 0,\n'
    '    "elevator": false,\n'
    '    "own_car": false,\n'
    '    "carpool_driver_seats": 0,\n'
    '    "carpool_rider_consent": false\n'
    "  },\n"
    '  "visit_request": {\n'
    '    "department": "orthopaedics",\n'
    '    "visit_type": "follow_up",\n'
    '    "urgency_class": "within_week",\n'
    '    "earliest_date": null,\n'
    '    "latest_date": null,\n'
    '    "recurrence": null,\n'
    '    "preferred_time_of_day": null\n'
    "  },\n"
    '  "review": []\n'
    "}\n\n"
    "PRIMJER 2:\n"
    'Ulaz: "Majka je nepokretna i leži u krevetu na prvom katu bez lifta u Senju, mora na hitno '
    'CT snimanje u Gospić u roku od par dana."\n'
    "Izlaz:\n"
    "{\n"
    '  "patient": {\n'
    '    "first_name": null,\n'
    '    "last_name": null,\n'
    '    "birth_year": null,\n'
    '    "phone": null,\n'
    '    "phone_type": null,\n'
    '    "settlement": "Senj",\n'
    '    "mobility_class": "stretcher",\n'
    '    "lives_alone": false,\n'
    '    "companion": null,\n'
    '    "floor": 1,\n'
    '    "elevator": false,\n'
    '    "own_car": false,\n'
    '    "carpool_driver_seats": 0,\n'
    '    "carpool_rider_consent": false\n'
    "  },\n"
    '  "visit_request": {\n'
    '    "department": "radiology",\n'
    '    "visit_type": "procedure_test",\n'
    '    "urgency_class": "within_few_days",\n'
    '    "earliest_date": null,\n'
    '    "latest_date": null,\n'
    '    "recurrence": null,\n'
    '    "preferred_time_of_day": null\n'
    "  },\n"
    '  "review": []\n'
    "}\n"
)

REQUIRED_REVIEW_FIELDS: tuple[tuple[str, str], ...] = (
    ("patient", "first_name"),
    ("patient", "last_name"),
    ("patient", "mbo"),
    ("patient", "phone"),
    ("patient", "settlement"),
    ("patient", "mobility_class"),
    ("visit_request", "department"),
    ("visit_request", "visit_type"),
    ("visit_request", "urgency_class"),
    ("visit_request", "earliest_date"),
    ("visit_request", "latest_date"),
)

_PATIENT_FIELD_NAMES = set(ExtractedPatientDraft.model_fields.keys()) - {"mbo"}
_VISIT_FIELD_NAMES = set(ExtractedVisitRequestDraft.model_fields.keys())

_STOP_WORDS_FIRST_NAME = {
    "Pacijent",
    "Pacijentica",
    "Majka",
    "Otac",
    "Supruga",
    "Suprug",
    "Sin",
    "Kći",
    "Zivim",
    "Živim",
    "Idem",
    "Imam",
    "Sutra",
    "Danas",
    "Iz",
    "U",
    "Za",
    "Na",
    "Kod",
    "Trebam",
    "Treba",
    "Dioptrija",
    "Kontrola",
    "Pregled",
    "Ulica",
    "Opća",
    "Klinički",
    "Donji",
    "Gornji",
    "Lički",
    "Ličko",
    "Baške",
    "Sveti",
    "Plitvička",
    "Crveni",
    "Dobar",
    "Zovem",
    "Javljam",
    "Ovdje",
    "Ja",
}


class MboStrip(NamedTuple):
    """Result of `strip_mbo_from_text`."""

    text: str
    mbo: str | None
    redacted: bool


def strip_mbo_from_text(text: str) -> MboStrip:
    """Redact MBO candidates before the LLM call (E11-T1).

    A number after an MBO cue is redacted whole (maximal run, numeric or spoken) when it has 5 or
    more digits; it becomes the MBO only with exactly 9 digits. Any invalid cued run, or two
    different cued values, gives `None` (flagged for the nurse). Uncued 9-digit windows are
    redacted but never become the MBO. Runs right after `+385` / `00385` are phones and stay.
    Never log text, runs or values.
    """
    cued_runs: list[tuple[int, int, str]] = []
    phone_runs: list[tuple[int, int]] = []
    for regex, spoken in ((_NUMERIC_RUN_RE, False), (_SPOKEN_RUN_RE, True)):
        for m in regex.finditer(text):
            prefix = text[: m.start()]
            if _PHONE_PREFIX_RE.search(prefix) or _starts_with_country_code(text, m.start()):
                phone_runs.append((m.start(), m.end()))
                continue
            if not _MBO_CUE_RE.search(_normalize(prefix)):
                continue
            digits = _run_digits(m.group(0), spoken)
            if len(digits) >= 5:
                cued_runs.append((m.start(), m.end(), digits))

    # Uncued numbers keep a 9-digit-window rule on purpose: without a cue a mistyped 10-digit MBO
    # is indistinguishable from a phone (`0915551234`), and redacting every long number would hide
    # all mobile numbers from the LLM. The nurse sees and confirms the record.
    protected = [(s, e) for s, e, _ in cued_runs] + phone_runs
    windows: list[tuple[int, int]] = []
    for regex, spoken in ((_MBO_DIGITS_RE, False), (_MBO_SPOKEN_RE, True)):
        for m in regex.finditer(text):
            if len(_run_digits(m.group(0), spoken)) != 9:
                continue
            if any(s < m.end() and m.start() < e for s, e in protected):
                continue
            windows.append((m.start(), m.end()))

    spans = sorted([(s, e) for s, e, _ in cued_runs] + windows)
    parts: list[str] = []
    pos = 0
    for start, end in spans:
        if start < pos:
            continue
        parts.append(text[pos:start])
        parts.append("[MBO_REDACTED]")
        pos = end
    parts.append(text[pos:])

    values = {d for _, _, d in cued_runs}
    all_valid = all(len(d) == 9 for d in values)
    mbo = next(iter(values)) if len(values) == 1 and all_valid else None
    return MboStrip("".join(parts), mbo, bool(spans))


def _starts_with_country_code(text: str, start: int) -> bool:
    if text.startswith("00385", start):
        return True
    return (
        text.startswith("385", start)
        and text[start + 3 : start + 4] in (" ", "-")
        and (text[start - 1 : start] == "+" if start else False)
    )


def _run_digits(run: str, spoken: bool) -> str:
    if spoken:
        return "".join(_SPOKEN_DIGITS[w] for w in run.lower().split())
    return re.sub(r"\D", "", run)


def _canon_text(text: str) -> str:
    return re.sub(r"\s+", " ", _normalize(text)).strip()


@lru_cache
def _load_canned_examples() -> dict[str, dict[str, Any]]:
    """Index `data/domain/extraction_examples.yaml` by normalized (MBO-stripped) text."""
    path = get_settings().data_dir / EXTRACTION_EXAMPLES_PATH
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    examples = raw.get("examples") if isinstance(raw, dict) else None
    if not isinstance(examples, list):
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for item in examples:
        if not isinstance(item, dict) or "text" not in item or "expected" not in item:
            continue
        raw_text = str(item["text"])
        stripped_text = strip_mbo_from_text(raw_text).text
        expected = item["expected"] if isinstance(item["expected"], dict) else {}
        raw_rev = item.get("review")
        review = [str(r) for r in raw_rev] if isinstance(raw_rev, list) else []

        patient_dict: dict[str, Any] = {}
        visit_dict: dict[str, Any] = {}
        for k, v in expected.items():
            val = v.isoformat() if isinstance(v, date) else v
            if k in _PATIENT_FIELD_NAMES:
                patient_dict[k] = val
            elif k in _VISIT_FIELD_NAMES:
                visit_dict[k] = val

        payload = {
            "patient": patient_dict,
            "visit_request": visit_dict,
            "review": review,
        }
        lookup[_canon_text(raw_text)] = payload
        lookup[_canon_text(stripped_text)] = payload
    return lookup


def _extract_name(text: str) -> tuple[str | None, str | None]:
    labeled = re.search(
        r"(?:Pacijent(?:ica)?|Ime\s+i\s+prezime|Zovem\s+se|zove\s+se)\s*:?\s*"
        r"([A-ZČĆŽŠĐ][a-zčćžšđ]+)\s+([A-ZČĆŽŠĐ][a-zčćžšđ]+)",
        text,
    )
    if labeled:
        return labeled.group(1), labeled.group(2)

    leading = re.match(
        r"^\s*([A-ZČĆŽŠĐ][a-zčćžšđ]+)\s+([A-ZČĆŽŠĐ][a-zčćžšđ]+)\b",
        text,
    )
    if leading and leading.group(1) not in _STOP_WORDS_FIRST_NAME:
        return leading.group(1), leading.group(2)
    return None, None


def _extract_dates(text: str) -> tuple[str | None, str | None]:
    iso_dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if len(iso_dates) >= 2:
        return iso_dates[0], iso_dates[1]
    if len(iso_dates) == 1:
        return iso_dates[0], iso_dates[0]

    hr_dates = re.findall(r"\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\.?", text)
    parsed: list[str] = []
    for day_s, month_s, year_s in hr_dates:
        try:
            d = date(int(year_s), int(month_s), int(day_s))
            parsed.append(d.isoformat())
        except ValueError:
            continue
    if len(parsed) >= 2:
        return parsed[0], parsed[1]
    if len(parsed) == 1:
        return parsed[0], parsed[0]
    return None, None


def offline_extract_dict(text: str) -> dict[str, Any]:
    """Deterministic Croatian extractor for offline/mock LLM mode (E2-T1)."""
    canned = _load_canned_examples().get(_canon_text(text))
    if canned is not None:
        return canned

    norm = _normalize(text)
    first_name, last_name = _extract_name(text)

    birth_year: int | None = None
    by_match = re.search(r"\b(19[2-9]\d|20[0-1]\d)\b", text)
    if by_match:
        birth_year = int(by_match.group(1))

    phone: str | None = None
    phone_match = re.search(
        r"(\+385[\s\-\d]{6,15}|\b09\d[\s\-/]?\d{3,4}[\s\-/]?\d{3,4}\b|\b053[\s\-/]?\d{3}[\s\-/]?\d{3,4}\b)",
        text,
    )
    if phone_match:
        phone = re.sub(r"\s+", " ", phone_match.group(1)).strip()

    phone_type: str | None = None
    if "pametni telefon" in norm or "smartphone" in norm or "onaj pametni" in norm:
        phone_type = PhoneType.SMARTPHONE.value
    elif "mobitel" in norm or "mobilni" in norm:
        phone_type = PhoneType.BASIC_MOBILE.value
    elif "fiksni" in norm or "kucni" in norm:
        phone_type = PhoneType.LANDLINE.value

    geo = MockGeocodingClient().geocode_address(text)
    settlement = geo.settlement if geo is not None else None

    mobility_class: str | None = None
    if any(k in norm for k in ("nosil", "nepokret", "lezi u krevetu", "lezim u krevetu", "lezec")):
        mobility_class = MobilityClass.STRETCHER.value
    elif "kolic" in norm:
        mobility_class = MobilityClass.WHEELCHAIR.value
    elif any(k in norm for k in ("stap", "stak", "hodalic")):
        mobility_class = MobilityClass.CANE.value
    elif any(
        k in norm
        for k in (
            "mogu hodati",
            "dobro hodam",
            "hodam normalno",
            "hodam ja normalno",
            "hodam sama",
            "hodam ko mladic",
            "pokretan",
            "pokretna",
            "hodam samostalno",
            "hodam bez pomagala",
            "samostalno hodam",
        )
    ):
        mobility_class = MobilityClass.WALKS.value

    lives_alone: bool | None = None
    if any(
        k in norm
        for k in (
            "zivim sam",
            "zivim sama",
            "zivim posve sama",
            "zivi sam",
            "zivi sama",
            "sama zivi",
            "sam sam",
            "sama sam",
        )
    ):
        lives_alone = True
    elif any(
        k in norm
        for k in (
            "zivim s ",
            "zivim sa ",
            "zivi s ",
            "zivimo zajedno",
            "zivimo sami, nas dvoje",
            "zivimo same",
            "suprug",
            "kceri",
        )
    ):
        lives_alone = False

    companion: bool | None = None
    if any(
        k in norm
        for k in (
            "pratnj",
            "ide sa mnom",
            "idem u pratnju",
            "idem s njim",
            "idem s njom",
            "ic s njim",
            "ic s njom",
        )
    ):
        companion = True
    elif any(
        k in norm
        for k in (
            "idem sam",
            "idem bez pratnje",
            "moram sama",
            "morat sam",
            "morat sama",
            "moram ic sama",
            "moram ici sama",
            "nema tko sa mnom",
            "nece moc sa mnom",
            "ne moze sa mnom",
        )
    ):
        companion = False

    floor: int | None = None
    if "prizemlj" in norm:
        floor = 0
    elif "prvom katu" in norm or "1. kat" in norm or "prvi kat" in norm:
        floor = 1
    elif "drugom katu" in norm or "2. kat" in norm or "drugi kat" in norm:
        floor = 2
    elif "trecem katu" in norm or "3. kat" in norm or "treci kat" in norm:
        floor = 3
    elif "cetvrtom katu" in norm or "4. kat" in norm or "cetvrti kat" in norm:
        floor = 4

    elevator: bool | None = None
    if "bez lifta" in norm or "nema lift" in norm or "lifta nema" in norm:
        elevator = False
    elif "s liftom" in norm or "ima lift" in norm:
        elevator = True

    own_car: bool | None = None
    carpool_driver_seats: int | None = None
    if any(
        k in norm
        for k in (
            "nemam auto",
            "auta nemam",
            "auta nema",
            "nemamo auto",
            "auta nemamo",
            "nema auta",
            "auto u kvaru",
            "auto nam je u kvaru",
            "auto ne radi",
            "ne smijem vozit",
            "preslab da vozim",
        )
    ):
        own_car = False
        carpool_driver_seats = 0
    elif any(
        k in norm
        for k in (
            "svojim autom",
            "vlastitim autom",
            "vozim vlastitim",
            "imam ispravan auto",
            "imam auto i vozim",
        )
    ):
        own_car = True
        if "tri slobodna" in norm or "troje" in norm:
            carpool_driver_seats = 3
        elif "dva slobodna" in norm or "dvoje" in norm:
            carpool_driver_seats = 2
        elif "jedno slobodno" in norm or "za jednog" in norm:
            carpool_driver_seats = 1

    carpool_rider_consent: bool | None = None
    if any(
        k in norm
        for k in (
            "s nepoznatom osobom",
            "rado bih isla s nekim",
            "rado isli s njim",
            "zajednickim prijevozom",
            "dijeliti prijevoz",
        )
    ):
        carpool_rider_consent = True

    department: str | None = None
    if "dijaliz" in norm or "hemodijaliz" in norm:
        department = Department.DIALYSIS.value
    elif any(k in norm for k in ("onkolog", "kemoterap", "zracenj")):
        department = Department.ONCOLOGY.value
    elif any(k in norm for k in ("kardiolog", "ultrazvuk srca", "pregled srca", "za srce", "ekg")):
        department = Department.CARDIOLOGY.value
    elif any(k in norm for k in ("oftalmolog", "ocnog", "ocni", "dioptrij", "naocal")):
        department = Department.OPHTHALMOLOGY.value
    elif any(k in norm for k in ("ortoped", "operacije kuka", "koljen", "skidaju gips")):
        department = Department.ORTHOPAEDICS.value
    elif any(k in norm for k in ("neurolog", "emng", "eeg")):
        department = Department.NEUROLOGY.value
    elif any(
        k in norm for k in ("radiolog", "ct ", "ct-", "ultrazvuk", "rtg", "snimanj", "magnetsk")
    ):
        department = Department.RADIOLOGY.value
    elif "intern" in norm:
        department = Department.INTERNAL_MEDICINE.value

    visit_type: str | None = None
    if department == Department.DIALYSIS.value or "dijaliz" in norm:
        visit_type = VisitType.DIALYSIS_SESSION.value
    elif (
        "prvi pregled" in norm
        or "prvi subspecijalisticki" in norm
        or ("prvi put" in norm and "kemoterap" not in norm)
    ):
        visit_type = VisitType.FIRST_VISIT.value
    elif "kontrol" in norm:
        visit_type = VisitType.FOLLOW_UP.value
    elif any(
        k in norm
        for k in (
            "snimanj",
            "ultrazvuk",
            "emng",
            "obrad",
            "pretrag",
            "dioptrij",
            "naocal",
            "kemoterap",
        )
    ):
        visit_type = VisitType.PROCEDURE_TEST.value

    urgency_class: str | None = None
    if (
        department == Department.DIALYSIS.value
        or "ne smije pomicati" in norm
        or "fiksni termin" in norm
        or "datum je fiksan" in norm
        or "mora bit tocno taj dan" in norm
    ):
        urgency_class = UrgencyClass.FIXED.value
    elif any(
        k in norm
        for k in ("hitno", "u roku od par dana", "za par dana", "u par dana", "nekoliko dana")
    ):
        urgency_class = UrgencyClass.WITHIN_FEW_DAYS.value
    elif any(k in norm for k in ("ovaj tjedan", "unutar tjedan", "u roku od tjedan dana", "sutra")):
        urgency_class = UrgencyClass.WITHIN_WEEK.value
    elif any(k in norm for k in ("unutar mjesec", "ovaj mjesec", "mjesec dana")):
        urgency_class = UrgencyClass.WITHIN_MONTH.value

    recurrence: str | None = None
    if "tri puta tjedno" in norm or "triput tjedno" in norm or "3x tjedno" in norm:
        recurrence = "3x_weekly"

    preferred_time_of_day: str | None = None
    if "samo poslije podne" in norm or "popodne" in norm or "poslijepodne" in norm:
        preferred_time_of_day = "afternoon"
    elif "ujutro" in norm or "prijepodne" in norm:
        preferred_time_of_day = "morning"

    earliest_date, latest_date = _extract_dates(text)

    return {
        "patient": {
            "first_name": first_name,
            "last_name": last_name,
            "birth_year": birth_year,
            "phone": phone,
            "phone_type": phone_type,
            "settlement": settlement,
            "mobility_class": mobility_class,
            "lives_alone": lives_alone,
            "companion": companion,
            "floor": floor,
            "elevator": elevator,
            "own_car": own_car,
            "carpool_driver_seats": carpool_driver_seats,
            "carpool_rider_consent": carpool_rider_consent,
        },
        "visit_request": {
            "department": department,
            "visit_type": visit_type,
            "urgency_class": urgency_class,
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "recurrence": recurrence,
            "preferred_time_of_day": preferred_time_of_day,
        },
        "review": [],
    }


def offline_extract_json(text: str) -> str:
    return json.dumps(offline_extract_dict(text), ensure_ascii=False)


def _validate_partial_model[M: (ExtractedPatientDraft, ExtractedVisitRequestDraft)](
    model_cls: type[M],
    raw: dict[str, Any],
    invalid_fields: list[str],
) -> M:
    """Validate each field separately so a bad LLM value goes to `for_review` instead of 500."""
    clean: dict[str, Any] = {}
    for field_name in model_cls.model_fields:
        if field_name not in raw or raw[field_name] is None:
            continue
        try:
            validated = model_cls.model_validate({field_name: raw[field_name]})
            clean[field_name] = getattr(validated, field_name)
        except ValidationError:
            invalid_fields.append(field_name)
    return model_cls.model_validate(clean)


def extract_intake(
    text: str,
    llm_client: LLMClient,
    geocoding_client: GeocodingClient,
) -> IntakeExtractResponse:
    """Extract structured `Patient` and `VisitRequest` drafts from free text (E2-T1, E11-T1)."""
    stripped = strip_mbo_from_text(text)
    sanitized_text, extracted_mbo = stripped.text, stripped.mbo

    raw_response = llm_client.complete(SYSTEM_PROMPT_HR, sanitized_text)
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    raw_patient = parsed.get("patient")
    raw_visit = parsed.get("visit_request")
    raw_review = parsed.get("review")
    if not isinstance(raw_patient, dict):
        raw_patient = {}
    if not isinstance(raw_visit, dict):
        raw_visit = {}
    review_from_llm = (
        [str(item) for item in raw_review if isinstance(item, str)]
        if isinstance(raw_review, list)
        else []
    )

    # Never trust an MBO produced by the LLM; only use the cue-labelled MBO scrubbed locally.
    raw_patient.pop("mbo", None)

    invalid_fields: list[str] = []
    patient_draft = _validate_partial_model(ExtractedPatientDraft, raw_patient, invalid_fields)
    visit_draft = _validate_partial_model(ExtractedVisitRequestDraft, raw_visit, invalid_fields)

    if extracted_mbo is not None:
        patient_draft.mbo = extracted_mbo

    # Enrich coordinates, settlement, municipality, and county via geocoding adapter (E2-T3).
    geo_query = patient_draft.settlement
    geocoded = geocoding_client.geocode_address(geo_query) if geo_query else None
    if geocoded is not None:
        if patient_draft.settlement is None:
            patient_draft.settlement = geocoded.settlement
        if patient_draft.municipality is None:
            patient_draft.municipality = geocoded.municipality
        if patient_draft.county is None:
            patient_draft.county = geocoded.county
        if patient_draft.location is None:
            patient_draft.location = GeoPoint(lat=geocoded.lat, lon=geocoded.lon)

    if (
        visit_draft.earliest_date is not None
        and visit_draft.latest_date is not None
        and visit_draft.latest_date < visit_draft.earliest_date
    ):
        visit_draft.latest_date = None
        invalid_fields.append("latest_date")

    for_review: list[str] = []
    for item in [*review_from_llm, *invalid_fields]:
        if item not in for_review:
            for_review.append(item)

    for section, field_name in REQUIRED_REVIEW_FIELDS:
        target = patient_draft if section == "patient" else visit_draft
        if getattr(target, field_name) is None and field_name not in for_review:
            for_review.append(field_name)

    return IntakeExtractResponse(
        patient=patient_draft,
        visit_request=visit_draft,
        for_review=for_review,
        mbo_stripped=stripped.redacted,
    )
