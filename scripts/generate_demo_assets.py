"""
Generate deterministic demo claim bundles for ClaimPilot frontend testing.

Creates 3 synthetic claim bundles, each containing:
  - metadata.json          (claimant, policy, scenario, expected outcome)
  - claim_form.pdf         (ACORD-like PDF via AcordPDF)
  - 2 placeholder JPEGs    (colored rectangles with damage labels via Pillow)
  - voice_statement.txt    (transcript; audio is optional)

Usage:
    python scripts/generate_demo_assets.py
    python scripts/generate_demo_assets.py --output-dir demo_assets/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Allow running directly: python scripts/generate_demo_assets.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from evaluation.generate_acord_synthetic import AcordFormData, AcordPDF, render_pdf

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    {
        "folder": "claim_001_approve",
        "scenario": "Minor front damage — straightforward approval",
        "expected_outcome": "APPROVED",
        "form_data": AcordFormData(
            applicant_first_name="Maria",
            applicant_last_name="Thompson",
            applicant_street="1247 Oak Ave",
            applicant_city="Springfield",
            applicant_state="IL",
            applicant_zip="62704",
            applicant_phone="(217) 555-0142",
            applicant_email="maria.thompson@gmail.com",
            policy_number="AT42093871",
            policy_effective_date="2025-06-01",
            policy_expiry_date="2026-05-31",
            vehicle_year=2022,
            vehicle_make="Toyota",
            vehicle_model="Camry",
            vehicle_vin="4T1G11AK5NU053284",
            vehicle_color="White",
            loss_date="2026-03-15",
            loss_time="09:30",
            loss_location="Springfield, IL",
            loss_description="Front-end collision with deer on rural road. Bumper and hood damage. Airbags did not deploy.",
            estimated_repair_amount=3400.00,
            coverage_type="Collision",
            claimant_first_name="Maria",
            claimant_last_name="Thompson",
            claimant_phone="(217) 555-0142",
            claimant_email="maria.thompson@gmail.com",
        ),
        "image_labels": [
            ("FRONT BUMPER — MINOR DAMAGE", (180, 60, 60)),
            ("HOOD — DENT AND SCRATCHES", (200, 180, 160)),
        ],
        "voice_statement": (
            "My name is Maria Thompson. On March 15th around 9:30 AM I was driving "
            "northbound on Rural Route 5 just outside Springfield when a deer ran "
            "across the road. I hit the brakes but couldn't stop in time. The front "
            "bumper hit the deer. The car has damage to the front bumper and there's "
            "a dent on the hood. The airbags didn't go off. I was the only person in "
            "the vehicle and I wasn't injured. I called the police and they filed a "
            "report at the scene."
        ),
    },
    {
        "folder": "claim_002_escalate",
        "scenario": "Rear-end collision with high repair estimate — escalate for review",
        "expected_outcome": "ESCALATED",
        "form_data": AcordFormData(
            applicant_first_name="James",
            applicant_last_name="Chen",
            applicant_street="893 Maple Dr",
            applicant_city="San Jose",
            applicant_state="CA",
            applicant_zip="95112",
            applicant_phone="(408) 555-0276",
            applicant_email="james.chen@outlook.com",
            policy_number="JC77120456",
            policy_effective_date="2025-01-15",
            policy_expiry_date="2026-01-14",
            vehicle_year=2024,
            vehicle_make="BMW",
            vehicle_model="5 Series",
            vehicle_vin="WBA53FJ09R8C49216",
            vehicle_color="Black",
            loss_date="2026-01-10",
            loss_time="17:45",
            loss_location="San Jose, CA",
            loss_description="Rear-end collision at stoplight. Other vehicle failed to stop. Significant trunk and rear bumper damage. Frame may be bent.",
            estimated_repair_amount=18750.00,
            coverage_type="Collision",
            claimant_first_name="James",
            claimant_last_name="Chen",
            claimant_phone="(408) 555-0276",
            claimant_email="james.chen@outlook.com",
        ),
        "image_labels": [
            ("REAR BUMPER — SIGNIFICANT IMPACT", (60, 60, 180)),
            ("TRUNK — CRUSHED, FRAME POSSIBLY BENT", (100, 100, 140)),
        ],
        "voice_statement": (
            "Hi, I'm James Chen. On January 10th, I was stopped at the traffic light "
            "on Stevens Creek Boulevard near the Valco mall when another car slammed "
            "into the back of my BMW. The impact was hard enough to push my car "
            "forward about ten feet. The rear bumper is badly damaged, the trunk is "
            "crushed and won't close, and the body shop says the frame might be bent. "
            "The other driver admitted fault at the scene. The repair estimate came "
            "back at eighteen thousand seven hundred and fifty dollars. My policy "
            "number is JC77120456."
        ),
    },
    {
        "folder": "claim_003_fraud_review",
        "scenario": "Inconsistent damage description — flagged for fraud review",
        "expected_outcome": "FRAUD_REVIEW",
        "form_data": AcordFormData(
            applicant_first_name="Diana",
            applicant_last_name="Brooks",
            applicant_street="42 Sunset Blvd",
            applicant_city="Miami",
            applicant_state="FL",
            applicant_zip="33101",
            applicant_phone="(305) 555-0398",
            applicant_email="diana.brooks@yahoo.com",
            policy_number="DB55309128",
            policy_effective_date="2025-09-01",
            policy_expiry_date="2026-08-31",
            vehicle_year=2021,
            vehicle_make="Ford",
            vehicle_model="Mustang",
            vehicle_vin="1FA6P8CF0M5107293",
            vehicle_color="Red",
            loss_date="2026-04-25",
            loss_time="22:15",
            loss_location="Miami, FL",
            loss_description="Hit-and-run in parking lot. Damage to rear bumper and trunk.",
            estimated_repair_amount=8500.00,
            coverage_type="Collision",
            claimant_first_name="Diana",
            claimant_last_name="Brooks",
            claimant_phone="(305) 555-0398",
            claimant_email="diana.brooks@yahoo.com",
        ),
        "image_labels": [
            ("REAR BUMPER — DAMAGE REPORTED", (180, 60, 180)),
            ("DRIVER SIDE — SCRATCHES INCONSISTENT WITH CLAIM", (140, 100, 160)),
        ],
        "voice_statement": (
            "Uh, my name is Diana Brooks. I, uh, I was at the, the shopping center "
            "on, um, I think it was Friday night, around ten, and when I came back "
            "to my car there was damage. Someone must have hit it and drove away. "
            "It's a red Ford Mustang. The, uh, the back bumper is damaged and the "
            "trunk has some issues too. And there are scratches on the driver side "
            "door, but I think those were already there. No, wait, actually those "
            "might be new too. I'm not sure. I didn't see it happen. There were no "
            "witnesses. I filed a police report online the next day."
        ),
    },
]


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

def _create_placeholder_jpeg(
    label: str,
    color: tuple[int, int, int],
    path: Path,
    width: int = 640,
    height: int = 480,
) -> Path:
    """Create a small placeholder JPEG with a colored rectangle and text label."""
    img = Image.new("RGB", (width, height), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw colored rectangle in center
    margin = 60
    draw.rectangle(
        [margin, margin, width - margin, height - margin],
        fill=color,
        outline=(0, 0, 0),
        width=2,
    )

    # Draw label text — try a basic font, fall back to default
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # Center text in the rectangle
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (width - text_w) / 2
    text_y = (height - text_h) / 2
    draw.text((text_x, text_y), label, fill=(255, 255, 255), font=font)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "JPEG", quality=85)
    return path


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------

def generate_demo_assets(output_dir: Path | None = None) -> dict[str, Any]:
    """Generate all 3 demo claim bundles. Returns summary dict."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "demo_assets"

    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    for scenario in SCENARIOS:
        folder = output_dir / scenario["folder"]
        folder.mkdir(parents=True, exist_ok=True)

        # 1. metadata.json
        metadata = {
            "claimant_name": scenario["form_data"].claimant_name,
            "policy_number": scenario["form_data"].policy_number,
            "claim_id": scenario["folder"],
            "scenario": scenario["scenario"],
            "expected_outcome": scenario["expected_outcome"],
            "files": {
                "claim_form": "claim_form.pdf",
                "photos": [f"photo_{i + 1}.jpg" for i in range(len(scenario["image_labels"]))],
                "voice_transcript": "voice_statement.txt",
                "audio": "optional — not included in this pack",
            },
        }
        (folder / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

        # 2. claim_form.pdf
        render_pdf(scenario["form_data"], folder / "claim_form.pdf")

        # 3. placeholder JPEGs
        for i, (label, color) in enumerate(scenario["image_labels"], start=1):
            _create_placeholder_jpeg(label, color, folder / f"photo_{i}.jpg")

        # 4. voice_statement.txt
        (folder / "voice_statement.txt").write_text(scenario["voice_statement"] + "\n")

        generated.append(scenario["folder"])

    return {
        "output_dir": str(output_dir),
        "bundles": generated,
        "total_claims": len(generated),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic demo claim bundles for ClaimPilot",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: demo_assets/ at project root)",
    )
    args = parser.parse_args()
    result = generate_demo_assets(output_dir=args.output_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
