from app.discovery.deduplicator import is_confident_duplicate


def test_deduplication_confident_matches_and_safe_non_merges():
    a = {
        "full_name": "Dr. Duplicate Test Alpha",
        "organization_name": "Unit Public School Trust",
        "location": "Mumbai, India",
        "primary_source": "src_a",
        "source_record_id": "id-1",
    }
    b_same_org = {
        "full_name": "Duplicate Test Alpha",
        "organization_name": "Unit Public School Trust",
        "location": "Mumbai, India",
        "primary_source": "src_b",
        "source_record_id": "id-2",
    }
    dup, conf, reason = is_confident_duplicate(a, b_same_org)
    assert dup is True
    assert conf >= 0.90
    assert reason == "normalized_name_and_organization"

    # Same name at a completely different org with low bio similarity must NOT auto-merge
    c_diff_person = {
        "full_name": "Duplicate Test Alpha",
        "organization_name": "Apex FinTech Solutions",
        "location": "Chennai, India",
        "primary_source": "src_c",
        "source_record_id": "id-3",
    }
    dup2, conf2, reason2 = is_confident_duplicate(a, c_diff_person, [1.0, 0.0], [0.0, 1.0])
    assert dup2 is False
    assert conf2 < 0.6
    assert reason2 == "same_name_insufficient_identity_confidence"
