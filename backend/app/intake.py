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

from app.adapters.geocoding import GeocodingClient, _normalize
from app.adapters.llm import LLMClient
from app.config import get_settings
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
    "   Broj propuštenih posjeta u zadnjih 12 mjeseci (`missed_visits_last_year`) navedi samo "
    "ako je izričito rečen.\n"
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
    'Ulaz: "Pacijent Ivan Kovačević (1958.), Otočac, tel +385 00 000 0002, mobitel na tipke. '
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
    '    "elevator": null,\n'
    '    "own_car": null,\n'
    '    "carpool_driver_seats": null,\n'
    '    "carpool_rider_consent": null,\n'
    '    "missed_visits_last_year": null\n'
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
    '    "lives_alone": null,\n'
    '    "companion": null,\n'
    '    "floor": 1,\n'
    '    "elevator": false,\n'
    '    "own_car": null,\n'
    '    "carpool_driver_seats": null,\n'
    '    "carpool_rider_consent": null,\n'
    '    "missed_visits_last_year": null\n'
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
def load_offline_answers() -> dict[str, dict[str, Any]]:
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


def offline_answer(text: str) -> str:
    """Canned JSON answer for the offline mock LLM (E2-T1); `"{}"` for any unscripted text.

    The mock never guesses (rule 5): unknown text yields no fields, so every required field
    lands in `for_review`. Free typing needs `LLM_BACKEND=api`.
    """
    canned = load_offline_answers().get(_canon_text(text))
    return json.dumps(canned if canned is not None else {}, ensure_ascii=False)


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
