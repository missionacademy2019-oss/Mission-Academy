"""Tests for credential_access.py — pure logic only, no Telegram, no I/O."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from credential_access import (
    check_enrollment, check_phone, new_free_record, is_allowed,
    needs_credentials, approve_credential, start_phone_path,
    record_qualified_referral, learner_view,
)

DAY = 86400
T0 = 1_700_000_000


def test_free_includes_trial():
    r = new_free_record(T0)
    assert r["status"] == "free"
    assert r["free_end"] - r["free_start"] == 90 * DAY
    assert is_allowed(r, T0 + 89 * DAY)
    assert not is_allowed(r, T0 + 91 * DAY)
    assert needs_credentials(r, T0 + 91 * DAY)
    print("free_includes_trial ok")


def test_enrollment_approve_and_gate():
    r = new_free_record(T0)
    r, err = approve_credential(r, "IGNOU", "MAEG", "Year 1", "enrollment", "123456789", T0)
    assert err is None and r["status"] == "credentialed"
    assert r["access_end"] == T0 + 90 * DAY
    assert is_allowed(r, T0 + 90 * DAY)
    assert not is_allowed(r, T0 + 91 * DAY)
    print("enrollment_approve ok")


def test_format_checks():
    assert check_enrollment("12345678") == "12345678"
    assert check_enrollment("123") is None
    assert check_enrollment("abc123456") is None
    assert check_phone("86066 56245") == "8606656245"
    assert check_phone("+91 8606656245") == "8606656245"
    assert check_phone("5606656245") is None
    assert check_phone("12345") is None
    print("format_checks ok")


def test_phone_needs_referrals():
    r = new_free_record(T0)
    r, err = approve_credential(r, "IGNOU", "MAEG", "Year 1", "phone", "8606656245", T0)
    assert err == "phone_needs_referrals" and r["status"] == "free"
    r, err = start_phone_path(r, "IGNOU", "MAEG", "Year 1", "8606656245", T0)
    assert err is None and r["status"] == "phone_pending_referral"
    # 9 qualified referrals: still pending
    for _ in range(9):
        ref = new_free_record(T0)
        ref, _ = approve_credential(ref, "IGNOU", "MAEG", "Year 1", "enrollment", "123456789", T0)
        r, approved = record_qualified_referral(r, ref, T0)
        assert not approved
    assert r["referral_count"] == 9 and r["status"] == "phone_pending_referral"
    # Wrong-course referral does not count
    wrong = new_free_record(T0)
    wrong, _ = approve_credential(wrong, "IGNOU", "MBA", "Sem 1", "enrollment", "123456789", T0)
    r, approved = record_qualified_referral(r, wrong, T0)
    assert r["referral_count"] == 9 and not approved
    # 10th qualified referral approves
    ref = new_free_record(T0)
    ref, _ = approve_credential(ref, "IGNOU", "MAEG", "Year 1", "enrollment", "123456789", T0)
    r, approved = record_qualified_referral(r, ref, T0)
    assert approved and r["status"] == "credentialed" and r["referral_count"] == 10
    print("phone_referrals ok")


def test_learner_view_erases_credential():
    r = new_free_record(T0)
    r, _ = approve_credential(r, "IGNOU", "MAEG", "Year 1", "enrollment", "123456789", T0)
    view = learner_view(r)
    assert "credential_value" not in view
    assert "123456789" not in str(view)
    assert view["course"] == "MAEG" and view["status"] == "credentialed"
    print("learner_erasure ok")


if __name__ == "__main__":
    test_free_includes_trial()
    test_enrollment_approve_and_gate()
    test_format_checks()
    test_phone_needs_referrals()
    test_learner_view_erases_credential()
    print("ALL CREDENTIAL TESTS PASSED")
