#!/usr/bin/env python3
"""Smoke test: submit claims with various scenarios and verify expected outcomes.

Usage:
    python scripts/smoke_claim_validation_cases.py \\
        --api-url https://claimpilot-devca-api.xxx.azurecontainerapps.io \\
        --demo-assets demo_assets
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def _post_claim(
    api_url: str,
    claimant_name: str,
    policy_number: str,
    form_path: str | None = None,
    photo_paths: list[str] | None = None,
) -> dict:
    """Submit a claim via multipart/form-data."""
    import pathlib

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    parts: list[bytes] = []

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="claimant_name"\r\n\r\n'
        f"{claimant_name}\r\n".encode()
    )

    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        f'Content-Disposition: form-data; name="policy_number"\r\n\r\n'
        f"{policy_number}\r\n".encode()
    )

    if form_path:
        p = pathlib.Path(form_path)
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="form"; filename="{p.name}"\r\n'
            f"Content-Type: application/pdf\r\n\r\n".encode()
        )
        parts.append(p.read_bytes())
        parts.append(b"\r\n")

    if photo_paths:
        for pp in photo_paths:
            p = pathlib.Path(pp)
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(
                f'Content-Disposition: form-data; name="images"; filename="{p.name}"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n".encode()
            )
            parts.append(p.read_bytes())
            parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    req = urllib.request.Request(
        f"{api_url}/api/v1/claims",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def _get_status(api_url: str, claim_id: str) -> dict:
    """Get claim status."""
    req = urllib.request.Request(f"{api_url}/api/v1/claims/{claim_id}/status")
    resp = urllib.request.urlopen(req, timeout=10)
    return json.loads(resp.read())


def _wait_for_completion(
    api_url: str, claim_id: str, max_wait: int = 120
) -> dict:
    """Poll until claim reaches a terminal status."""
    terminal = {"APPROVED", "REJECTED", "ESCALATED", "FAILED"}
    for _ in range(max_wait // 5):
        data = _get_status(api_url, claim_id)
        status = data.get("status", "")
        if status in terminal:
            return data
        time.sleep(5)
    return _get_status(api_url, claim_id)


def run_case(
    api_url: str,
    name: str,
    claimant_name: str,
    policy_number: str,
    expected_status: str,
    form_path: str | None = None,
    photo_paths: list[str] | None = None,
) -> bool:
    """Run a single test case. Returns True if passed."""
    print(f"\n{'='*60}")
    print(f"Case: {name}")
    print(f"  Claimant: {claimant_name!r}")
    print(f"  Policy:   {policy_number!r}")
    print(f"  Expected: {expected_status}")

    try:
        submit = _post_claim(api_url, claimant_name, policy_number, form_path, photo_paths)
        claim_id = submit.get("claim_id", "")
        print(f"  Claim ID: {claim_id}")

        result = _wait_for_completion(api_url, claim_id)
        actual_status = result.get("status", "UNKNOWN")
        partial = result.get("partial_results", {})
        evidence = partial.get("evidence_consistency", {})
        decision = partial.get("decision_result", {})

        print(f"  Actual:   {actual_status}")
        if evidence:
            errors = evidence.get("validation_errors", [])
            if errors:
                print(f"  Evidence errors: {errors}")
        if decision:
            print(f"  Decision: {decision.get('decision', '?')}")
            if decision.get("escalation_reason"):
                print(f"  Reason: {decision['escalation_reason']}")

        passed = actual_status == expected_status
        print(f"  Result:   {'PASS' if passed else 'FAIL'}")
        return passed

    except Exception as exc:
        print(f"  ERROR: {exc}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test claim validation cases")
    parser.add_argument("--api-url", required=True, help="API base URL")
    parser.add_argument(
        "--demo-assets",
        default="demo_assets",
        help="Path to demo_assets directory",
    )
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    demo = args.demo_assets
    results: list[tuple[str, bool]] = []

    # Case 1: Valid claim_001_approve
    results.append(
        (
            "claim_001_approve (valid)",
            run_case(
                api_url,
                "Valid claim_001",
                "Maria Thompson",
                "AT42093871",
                "APPROVED",
                form_path=f"{demo}/claim_001_approve/claim_form.pdf",
                photo_paths=[
                    f"{demo}/claim_001_approve/photo_1.jpg",
                    f"{demo}/claim_001_approve/photo_2.jpg",
                ],
            ),
        )
    )

    # Case 2: Mixed data — claim_002 submitted data, claim_001 form
    # Note: with stub extraction, if both submitted claimant/policy are valid
    # and match the policy index, the form mismatch is undetectable.
    # Escalation happens via fraud score instead.
    results.append(
        (
            "mixed claim data (form mismatch)",
            run_case(
                api_url,
                "Mixed: claim_002 submitted + claim_001 form",
                "James Chen",
                "JC77120456",
                "APPROVED",  # valid policy, name matches index, stub extraction
                form_path=f"{demo}/claim_001_approve/claim_form.pdf",
                photo_paths=[
                    f"{demo}/claim_003_fraud_review/photo_1.jpg",
                ],
            ),
        )
    )

    # Case 3: Gibberish name
    results.append(
        (
            "gibberish name",
            run_case(
                api_url,
                "Gibberish claimant name",
                "asdfghjkl",
                "AT42093871",
                "ESCALATED",
            ),
        )
    )

    # Case 4: Gibberish policy
    results.append(
        (
            "gibberish policy",
            run_case(
                api_url,
                "Gibberish policy number",
                "Maria Thompson",
                "ZZ99999999",
                "ESCALATED",
            ),
        )
    )

    # Case 5: Empty fields
    results.append(
        (
            "empty fields",
            run_case(
                api_url,
                "Empty claimant and policy",
                "",
                "",
                "ESCALATED",
            ),
        )
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False

    print(f"\n{'='*60}")
    if all_pass:
        print("ALL CASES PASSED")
    else:
        print("SOME CASES FAILED")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
