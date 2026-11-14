"""Free-text intake extraction and MBO privacy guard (E2-T1, E11-T1)."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.adapters.geocoding import GeocodingClient, MockGeocodingClient, _normalize
from app.adapters.llm import LLMClient
from app.models import (
    Department,
    MobilityClass,
    PhoneType,
    TransportEntitlement,
    UrgencyClass,
    VisitType,
)
from app.schemas import (
    ExtractedPatientDraft,
    ExtractedVisitRequestDraft,
    GeoPoint,
    IntakeExtractResponse,
)

# Matches any standalone 9-digit MBO sequence (optionally preceded by "MBO:" / "MBO").
_MBO_TOKEN_RE = re.compile(r"\b(\d{9})\b")

SYSTEM_PROMPT_HR = (
    "Ti si medicinski administrativni asistent za sustav OptiCare u Ličko-senjskoj županiji.\n"
    "Iz slobodnog teksta (bilješke medicinske sestre ili opisa pacijenta) izdvoji strukturirane "
    "podatke prema shemama `patient` i `visit_request`.\n\n"
    "PRAVILA:\n"
    '1. Odgovori ISKLJUČIVO valjanim JSON objektom s ključevima `"patient"` i `"visit_request"`.\n'
    "2. Nikada ne nagađaj podatke koji nisu navedeni u tekstu — za svako nepoznato polje vrati "
    "`null`.\n"
    "3. Dozvoljene vrijednosti šifrarnika:\n"
    '   - `mobility_class`: "walks" | "cane" | "wheelchair" | "stretcher"\n'
    '   - `phone_type`: "landline" | "basic_mobile" | "smartphone"\n'
    '   - `transport_entitlement`: "sanitetski" | "travel_order" | "none"\n'
    '   - `department`: "internal_medicine" | "cardiology" | "ophthalmology" | "orthopaedics" | '
    '"neurology" | "radiology" | "oncology" | "dialysis"\n'
    '   - `visit_type`: "first_visit" | "follow_up" | "procedure_test" | "dialysis_session"\n'
    '   - `urgency_class`: "fixed" | "within_few_days" | "within_week" | "within_month"\n'
    '   - `facility_key`: "ob_gospic" | "kbc_rijeka" | "kbc_zagreb"\n'
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
    '    "address": null,\n'
    '    "settlement": "Otočac",\n'
    '    "mobility_class": "wheelchair",\n'
    '    "lives_alone": false,\n'
    '    "companion": true,\n'
    '    "floor": 0,\n'
    '    "elevator": false,\n'
    '    "transport_entitlement": "sanitetski",\n'
    '    "own_car": false,\n'
    '    "carpool_driver_seats": 0,\n'
    '    "carpool_rider_consent": false\n'
    "  },\n"
    '  "visit_request": {\n'
    '    "facility_key": "ob_gospic",\n'
    '    "department": "orthopaedics",\n'
    '    "visit_type": "follow_up",\n'
    '    "urgency_class": "within_week",\n'
    '    "earliest_date": null,\n'
    '    "latest_date": null,\n'
    '    "recurrence": null,\n'
    '    "preferred_time_of_day": null\n'
    "  }\n"
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
    '    "address": null,\n'
    '    "settlement": "Senj",\n'
    '    "mobility_class": "stretcher",\n'
    '    "lives_alone": false,\n'
    '    "companion": null,\n'
    '    "floor": 1,\n'
    '    "elevator": false,\n'
    '    "transport_entitlement": "sanitetski",\n'
    '    "own_car": false,\n'
    '    "carpool_driver_seats": 0,\n'
    '    "carpool_rider_consent": false\n'
    "  },\n"
    '  "visit_request": {\n'
    '    "facility_key": "ob_gospic",\n'
    '    "department": "radiology",\n'
    '    "visit_type": "procedure_test",\n'
    '    "urgency_class": "within_few_days",\n'
    '    "earliest_date": null,\n'
    '    "latest_date": null,\n'
    '    "recurrence": null,\n'
    '    "preferred_time_of_day": null\n'
    "  }\n"
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
}


def strip_mbo_from_text(text: str) -> tuple[str, str | None]:
    """Remove all 9-digit MBO sequences before sending text to an LLM (E11-T1).

    Returns `(sanitized_text, first_extracted_mbo)`.
    """
    matches = _MBO_TOKEN_RE.findall(text)
    extracted_mbo = matches[0] if matches else None
    sanitized = _MBO_TOKEN_RE.sub("[MBO_REDACTED]", text)
    return sanitized, extracted_mbo


def _extract_name(text: str) -> tuple[str | None, str | None]:
    labeled = re.search(
        r"(?:Pacijent(?:ica)?|Ime\s+i\s+prezime|Zovem\s+se)\s*:?\s*"
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


def offline_extract_dict(text: str) -> dict[str, dict[str, Any]]:
    """Deterministic Croatian rule-based extractor for offline/mock LLM mode."""
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
    if "pametni telefon" in norm or "smartphone" in norm:
        phone_type = PhoneType.SMARTPHONE.value
    elif "mobitel" in norm or "mobilni" in norm:
        phone_type = PhoneType.BASIC_MOBILE.value
    elif "fiksni" in norm or "kucni telefon" in norm:
        phone_type = PhoneType.LANDLINE.value

    geo = MockGeocodingClient().geocode_address(text)
    settlement = geo.settlement if geo is not None else None

    mobility_class: str | None = None
    if any(k in norm for k in ("nosil", "nepokret", "lezi u krevetu", "lezec")):
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
            "pokretan",
            "pokretna",
            "hodam samostalno",
            "hodam bez pomagala",
            "samostalno hodam",
        )
    ):
        mobility_class = MobilityClass.WALKS.value

    lives_alone: bool | None = None
    if any(k in norm for k in ("zivim sam", "zivim sama", "zivi sam", "zivi sama")):
        lives_alone = True
    elif any(k in norm for k in ("zivim s ", "zivi s ", "suprug", "kceri")):
        lives_alone = False

    companion: bool | None = None
    if any(k in norm for k in ("pratnj", "ide sa mnom", "idem u pratnju")):
        companion = True

    floor: int | None = None
    if "prizemlj" in norm:
        floor = 0
    elif "prvom katu" in norm or "1. kat" in norm:
        floor = 1
    elif "drugom katu" in norm or "2. kat" in norm:
        floor = 2
    elif "trecem katu" in norm or "3. kat" in norm:
        floor = 3
    elif "cetvrtom katu" in norm or "4. kat" in norm:
        floor = 4

    elevator: bool | None = None
    if "bez lifta" in norm or "nema lift" in norm:
        elevator = False
    elif "s liftom" in norm or "ima lift" in norm:
        elevator = True

    own_car: bool | None = None
    carpool_driver_seats: int | None = None
    if any(k in norm for k in ("svojim autom", "vlastitim autom", "vozim vlastitim")):
        own_car = True
        if "tri slobodna" in norm or "troje" in norm:
            carpool_driver_seats = 3
        elif "dva slobodna" in norm or "dvoje" in norm:
            carpool_driver_seats = 2
        elif "jedno slobodno" in norm:
            carpool_driver_seats = 1
    elif any(k in norm for k in ("nemam auto", "nemamo automobil", "auto u kvaru")):
        own_car = False
        carpool_driver_seats = 0

    carpool_rider_consent: bool | None = None
    if any(
        k in norm
        for k in (
            "s nepoznatom osobom",
            "rado bih isla s nekim",
            "zajednickim prijevozom",
            "dijeliti prijevoz",
        )
    ):
        carpool_rider_consent = True

    transport_entitlement: str | None = None
    if mobility_class in (MobilityClass.WHEELCHAIR.value, MobilityClass.STRETCHER.value):
        transport_entitlement = TransportEntitlement.SANITETSKI.value
    elif "putni nalog" in norm:
        transport_entitlement = TransportEntitlement.TRAVEL_ORDER.value

    department: str | None = None
    if "dijaliz" in norm or "hemodijaliz" in norm:
        department = Department.DIALYSIS.value
    elif any(k in norm for k in ("onkolog", "kemoterap", "zracenj")):
        department = Department.ONCOLOGY.value
    elif any(k in norm for k in ("kardiolog", "ultrazvuk srca", "pregled srca", "ekg")):
        department = Department.CARDIOLOGY.value
    elif any(k in norm for k in ("oftalmolog", "ocnog", "ocni", "dioptrij", "naocal")):
        department = Department.OPHTHALMOLOGY.value
    elif any(k in norm for k in ("ortoped", "operacije kuka", "koljen")):
        department = Department.ORTHOPAEDICS.value
    elif any(k in norm for k in ("neurolog", "emng", "eeg")):
        department = Department.NEUROLOGY.value
    elif any(k in norm for k in ("radiolog", "ct ", "ct-", "ultrazvuk", "rtg", "snimanj")):
        department = Department.RADIOLOGY.value
    elif "intern" in norm:
        department = Department.INTERNAL_MEDICINE.value

    visit_type: str | None = None
    if department == Department.DIALYSIS.value or "dijaliz" in norm:
        visit_type = VisitType.DIALYSIS_SESSION.value
    elif "prvi pregled" in norm or "prvi subspecijalisticki" in norm:
        visit_type = VisitType.FIRST_VISIT.value
    elif "kontrol" in norm:
        visit_type = VisitType.FOLLOW_UP.value
    elif any(
        k in norm
        for k in ("snimanj", "ultrazvuk", "emng", "obrad", "pretrag", "dioptrij", "naocal")
    ):
        visit_type = VisitType.PROCEDURE_TEST.value

    urgency_class: str | None = None
    if (
        department == Department.DIALYSIS.value
        or "ne smije pomicati" in norm
        or "fiksni termin" in norm
    ):
        urgency_class = UrgencyClass.FIXED.value
    elif any(k in norm for k in ("hitno", "u roku od par dana", "za par dana", "nekoliko dana")):
        urgency_class = UrgencyClass.WITHIN_FEW_DAYS.value
    elif any(k in norm for k in ("ovaj tjedan", "unutar tjedan", "sutra")):
        urgency_class = UrgencyClass.WITHIN_WEEK.value
    elif any(k in norm for k in ("unutar mjesec", "ovaj mjesec", "mjesec dana")):
        urgency_class = UrgencyClass.WITHIN_MONTH.value

    facility_key: str | None = None
    if "rijek" in norm or "rijeci" in norm:
        facility_key = "kbc_rijeka"
    elif "zagreb" in norm or "rebro" in norm:
        facility_key = "kbc_zagreb"
    elif "gospic" in norm or "bolnic" in norm:
        facility_key = "ob_gospic"
    elif department == Department.ONCOLOGY.value:
        facility_key = "kbc_rijeka"
    elif department is not None:
        facility_key = "ob_gospic"

    recurrence: str | None = None
    if "tri puta tjedno" in norm or "3x tjedno" in norm:
        recurrence = "3x_weekly"

    preferred_time_of_day: str | None = None
    if "ujutro" in norm or "prijepodne" in norm:
        preferred_time_of_day = "morning"
    elif "popodne" in norm or "poslijepodne" in norm:
        preferred_time_of_day = "afternoon"

    earliest_date, latest_date = _extract_dates(text)

    return {
        "patient": {
            "first_name": first_name,
            "last_name": last_name,
            "birth_year": birth_year,
            "phone": phone,
            "phone_type": phone_type,
            "address": settlement,
            "settlement": settlement,
            "mobility_class": mobility_class,
            "lives_alone": lives_alone,
            "companion": companion,
            "floor": floor,
            "elevator": elevator,
            "transport_entitlement": transport_entitlement,
            "own_car": own_car,
            "carpool_driver_seats": carpool_driver_seats,
            "carpool_rider_consent": carpool_rider_consent,
        },
        "visit_request": {
            "facility_key": facility_key,
            "department": department,
            "visit_type": visit_type,
            "urgency_class": urgency_class,
            "earliest_date": earliest_date,
            "latest_date": latest_date,
            "recurrence": recurrence,
            "preferred_time_of_day": preferred_time_of_day,
        },
    }


def offline_extract_json(text: str) -> str:
    return json.dumps(offline_extract_dict(text), ensure_ascii=False)


def _validate_partial_model[M: (ExtractedPatientDraft, ExtractedVisitRequestDraft)](
    model_cls: type[M],
    raw: dict[str, Any],
    prefix: str,
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
            invalid_fields.append(f"{prefix}.{field_name}")
    return model_cls.model_validate(clean)


def extract_intake(
    text: str,
    llm_client: LLMClient,
    geocoding_client: GeocodingClient,
) -> IntakeExtractResponse:
    """Extract structured `Patient` and `VisitRequest` drafts from free text (E2-T1, E11-T1)."""
    sanitized_text, extracted_mbo = strip_mbo_from_text(text)

    raw_response = llm_client.complete(SYSTEM_PROMPT_HR, sanitized_text)
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    raw_patient = parsed.get("patient")
    raw_visit = parsed.get("visit_request")
    if not isinstance(raw_patient, dict):
        raw_patient = {}
    if not isinstance(raw_visit, dict):
        raw_visit = {}

    # Never trust an MBO produced by the LLM; only use the locally scrubbed 9-digit MBO.
    raw_patient.pop("mbo", None)

    invalid_fields: list[str] = []
    patient_draft = _validate_partial_model(
        ExtractedPatientDraft, raw_patient, "patient", invalid_fields
    )
    visit_draft = _validate_partial_model(
        ExtractedVisitRequestDraft, raw_visit, "visit_request", invalid_fields
    )

    if extracted_mbo is not None:
        patient_draft.mbo = extracted_mbo

    # Enrich coordinates, settlement, municipality, and county via geocoding adapter (E2-T3).
    geo_query = patient_draft.address or patient_draft.settlement or sanitized_text
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
        invalid_fields.append("visit_request.latest_date")

    for_review: list[str] = list(invalid_fields)
    for section, field_name in REQUIRED_REVIEW_FIELDS:
        target = patient_draft if section == "patient" else visit_draft
        key = f"{section}.{field_name}"
        if getattr(target, field_name) is None and key not in for_review:
            for_review.append(key)

    return IntakeExtractResponse(
        patient=patient_draft,
        visit_request=visit_draft,
        for_review=for_review,
        mbo_stripped=extracted_mbo is not None,
    )
