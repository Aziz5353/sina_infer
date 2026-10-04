import pytest

from src.util.phi import scrub_phi


@pytest.mark.parametrize(
    "text, secret, kind",
    [
        ("national id 1012345678 chest pain", "1012345678", "national_id"),
        ("iqama 2412345678 fever", "2412345678", "national_id"),
        ("call 0551234567 now", "0551234567", "phone"),
        ("call 055 123 4567 now", "055 123 4567", "phone"),
        ("call +966 55 123 4567 now", "+966 55 123 4567", "phone"),
        ("call 00966551234567 now", "00966551234567", "phone"),
        ("call 555-123-4567 now", "555-123-4567", "phone"),
        ("email dr.ahmad+x@hospital.sa please", "dr.ahmad+x@hospital.sa", "email"),
        ("DOB: 12/03/1980 asthma", "12/03/1980", "dob"),
        ("date of birth 1980-03-12 asthma", "1980-03-12", "dob"),
        ("born 12 March 1980 asthma", "1980", "dob"),
        ("seen on 03.04.2026 asthma", "03.04.2026", "date"),
    ],
)
def test_scrub_phi_removes_identifiers(text, secret, kind):
    scrubbed, removed = scrub_phi(text)
    assert secret not in scrubbed
    assert kind in removed


@pytest.mark.parametrize(
    "text",
    [
        "45-year-old male, BP 150/95, HR 110, SpO2 94%",
        "amoxicillin 500 mg every 8 hours for 5 days",
        "platelets 150000, troponin 0.04 ng/mL, INR 2.5",
        "acute chest pain differential diagnosis ACS management",
    ],
)
def test_scrub_phi_keeps_clinical_values(text):
    scrubbed, removed = scrub_phi(text)
    assert scrubbed == text
    assert removed == []
