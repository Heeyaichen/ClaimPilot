"""
Synthetic ACORD 1 Personal Auto Application form generator for ClaimPilot.

Generates realistic ACORD-like PDF forms with matching ground-truth JSON labels
and Azure Document Intelligence training-ready samples.

Usage:
    python -m evaluation.generate_acord_synthetic
    python -m evaluation.generate_acord_synthetic --count 100 --training-count 30 --seed 123
"""

from __future__ import annotations

import argparse
import json
import random
import string
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fpdf import FPDF

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACORD_TITLE = "ACORD 1 - Personal Auto Application"

MAKES = [
    "Toyota",
    "Honda",
    "Ford",
    "Chevrolet",
    "BMW",
    "Mercedes-Benz",
    "Tesla",
    "Hyundai",
    "Nissan",
    "Subaru",
]

MAKE_MODELS: dict[str, list[str]] = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Tacoma"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "HR-V"],
    "Ford": ["F-150", "Escape", "Explorer", "Mustang", "Edge"],
    "Chevrolet": ["Silverado", "Equinox", "Malibu", "Tahoe", "Traverse"],
    "BMW": ["3 Series", "5 Series", "X3", "X5", "7 Series"],
    "Mercedes-Benz": ["C-Class", "E-Class", "GLC", "GLE", "A-Class"],
    "Tesla": ["Model 3", "Model Y", "Model S", "Model X", "Cybertruck"],
    "Hyundai": ["Tucson", "Elantra", "Sonata", "Santa Fe", "Kona"],
    "Nissan": ["Altima", "Rogue", "Sentra", "Pathfinder", "Frontier"],
    "Subaru": ["Outback", "Forester", "Crosstrek", "Impreza", "Ascent"],
}

COLORS = [
    "White",
    "Black",
    "Silver",
    "Gray",
    "Red",
    "Blue",
    "Green",
    "Brown",
    "Beige",
    "Gold",
]

COVERAGE_TYPES = [
    "Collision",
    "Comprehensive",
    "Liability - Bodily Injury",
    "Liability - Property Damage",
    "Uninsured Motorist",
    "Underinsured Motorist",
    "Personal Injury Protection",
    "Medical Payments",
]

LOSS_DESCRIPTIONS = [
    "Rear-end collision at stoplight. Other vehicle failed to stop.",
    "Side impact collision at intersection. Other driver ran red light.",
    "Vehicle struck by falling tree branch during storm.",
    "Hail damage to roof, hood, and trunk.",
    "Windshield cracked by road debris on highway.",
    "Vehicle sideswiped while parked on street.",
    "Front-end collision with deer on rural road.",
    "Backing out of driveway, struck parked vehicle.",
    "Multi-vehicle pileup on icy freeway.",
    "Vandalism: side windows smashed and body scratched.",
    "Theft of vehicle recovered with interior damage.",
    "Flood damage to lower body and engine compartment.",
    "Fire damage originating from engine compartment.",
    "Rollover accident on wet curve.",
    "Hit-and-run in parking lot. Damage to rear bumper and trunk.",
    "T-bone collision in parking lot. Other vehicle failed to yield.",
    "Road debris caused tire blowout and rim damage.",
    "Vehicle keyed along both driver-side doors.",
    "Garage door closed onto roof of vehicle.",
    "Collision with utility pole after swerving to avoid animal.",
]

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Christopher",
    "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Margaret",
    "Mark", "Sandra", "Donald", "Ashley", "Steven", "Kimberly", "Paul",
    "Emily", "Andrew", "Donna", "Joshua", "Michelle",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
]

STREET_NAMES = [
    "Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd",
    "Elm St", "Washington Blvd", "Park Ave", "Lake Dr", "Hill Rd",
    "Sunset Blvd", "River Rd", "Forest Ave", "Spring St", "Valley Dr",
    "Highland Ave", "Meadow Ln", "Bay Rd", "Church St", "Broadway",
]

CITIES = [
    "Springfield", "Franklin", "Clinton", "Madison", "Georgetown",
    "Arlington", "Salem", "Fairview", "Chester", "Manchester",
    "Burlington", "Riverside", "Oakland", "Greenville", "Bristol",
    "Centerville", "Kingston", "Milton", "Newport", "Bridgewater",
]

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
    "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "OH", "OK", "OR", "PA", "SC", "TN", "TX", "UT", "VA",
    "WA", "WI", "WY",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rand_policy_number(rng: random.Random) -> str:
    """Generate a policy number: 2 uppercase letters + 8 digits."""
    letters = "".join(rng.choices(string.ascii_uppercase, k=2))
    digits = "".join(rng.choices(string.digits, k=8))
    return letters + digits


def _rand_vin(rng: random.Random) -> str:
    """Generate a realistic 17-character VIN."""
    # Real VINs exclude I, O, Q to avoid confusion with digits.
    valid_chars = string.digits + "ABCDEFGHJKLMNPRSTUVWXYZ"
    # WMI (first 3), VDS (chars 3-8), check digit (char 8), VIS (chars 9-16+)
    return "".join(rng.choices(valid_chars, k=17))


def _rand_phone(rng: random.Random) -> str:
    """Generate a US-style phone number."""
    area = "".join(rng.choices(string.digits, k=3))
    mid = "".join(rng.choices(string.digits, k=3))
    end = "".join(rng.choices(string.digits, k=4))
    return f"({area}) {mid}-{end}"


def _rand_email(first: str, last: str, rng: random.Random) -> str:
    """Generate a plausible email address."""
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "icloud.com"]
    local = f"{first.lower()}.{last.lower()}"
    # Sometimes append digits
    if rng.random() < 0.4:
        local += "".join(rng.choices(string.digits, k=rng.randint(1, 3)))
    return f"{local}@{rng.choice(domains)}"


def _rand_address(rng: random.Random) -> dict[str, str]:
    """Generate a US mailing address."""
    number = rng.randint(100, 9999)
    street = rng.choice(STREET_NAMES)
    city = rng.choice(CITIES)
    state = rng.choice(STATES)
    zipcode = "".join(rng.choices(string.digits, k=5))
    return {
        "street": f"{number} {street}",
        "city": city,
        "state": state,
        "zip": zipcode,
    }


def _currency(amount: float) -> str:
    """Format amount as currency string."""
    return f"${amount:,.2f}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class AcordFormData:
    """All fields for a single synthetic ACORD 1 form."""

    applicant_first_name: str
    applicant_last_name: str
    applicant_street: str
    applicant_city: str
    applicant_state: str
    applicant_zip: str
    applicant_phone: str
    applicant_email: str
    policy_number: str
    policy_effective_date: str
    policy_expiry_date: str
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    vehicle_vin: str
    vehicle_color: str
    loss_date: str
    loss_time: str
    loss_location: str
    loss_description: str
    estimated_repair_amount: float
    coverage_type: str
    claimant_first_name: str
    claimant_last_name: str
    claimant_phone: str
    claimant_email: str

    @property
    def applicant_name(self) -> str:
        return f"{self.applicant_first_name} {self.applicant_last_name}"

    @property
    def applicant_address(self) -> str:
        return (
            f"{self.applicant_street}, {self.applicant_city}, "
            f"{self.applicant_state} {self.applicant_zip}"
        )

    @property
    def claimant_name(self) -> str:
        return f"{self.claimant_first_name} {self.claimant_last_name}"

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dictionary of all field values (ground truth)."""
        d = asdict(self)
        # Add computed properties
        d["applicant_name"] = self.applicant_name
        d["applicant_address"] = self.applicant_address
        d["claimant_name"] = self.claimant_name
        d["estimated_repair_amount_formatted"] = _currency(self.estimated_repair_amount)
        return d


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_form_data(rng: random.Random) -> AcordFormData:
    """Generate a single random ACORD form data record."""
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    addr = _rand_address(rng)

    make = rng.choice(MAKES)
    model = rng.choice(MAKE_MODELS[make])
    year = rng.randint(2015, 2026)

    policy_eff_year = rng.randint(2023, 2025)
    policy_eff_month = rng.randint(1, 12)
    policy_eff_day = rng.randint(1, 28)
    effective = date(policy_eff_year, policy_eff_month, policy_eff_day)
    expiry = effective + timedelta(days=365)

    loss_offset = rng.randint(0, 364)
    loss_d = effective + timedelta(days=loss_offset)
    loss_hour = rng.randint(0, 23)
    loss_minute = rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])

    loss_city = rng.choice(CITIES)
    loss_state = rng.choice(STATES)

    claimant_first = rng.choice(FIRST_NAMES)
    claimant_last = rng.choice(LAST_NAMES)

    repair = round(rng.uniform(500, 25000), 2)

    return AcordFormData(
        applicant_first_name=first,
        applicant_last_name=last,
        applicant_street=addr["street"],
        applicant_city=addr["city"],
        applicant_state=addr["state"],
        applicant_zip=addr["zip"],
        applicant_phone=_rand_phone(rng),
        applicant_email=_rand_email(first, last, rng),
        policy_number=_rand_policy_number(rng),
        policy_effective_date=effective.isoformat(),
        policy_expiry_date=expiry.isoformat(),
        vehicle_year=year,
        vehicle_make=make,
        vehicle_model=model,
        vehicle_vin=_rand_vin(rng),
        vehicle_color=rng.choice(COLORS),
        loss_date=loss_d.isoformat(),
        loss_time=f"{loss_hour:02d}:{loss_minute:02d}",
        loss_location=f"{loss_city}, {loss_state}",
        loss_description=rng.choice(LOSS_DESCRIPTIONS),
        estimated_repair_amount=repair,
        coverage_type=rng.choice(COVERAGE_TYPES),
        claimant_first_name=claimant_first,
        claimant_last_name=claimant_last,
        claimant_phone=_rand_phone(rng),
        claimant_email=_rand_email(claimant_first, claimant_last, rng),
    )


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------


class AcordPDF(FPDF):
    """Minimal PDF generator that renders an ACORD-like form layout."""

    def __init__(self) -> None:
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)

    def header(self) -> None:
        pass  # Custom header drawn in build()

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def _section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(220, 220, 220)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT", fill=True)
        self.ln(2)

    def _field_row(self, label: str, value: str) -> None:
        self.set_font("Helvetica", "B", 10)
        label_w = 60
        self.cell(label_w, 7, label + ":", new_x="END", new_y="TOP")
        self.set_font("Helvetica", "", 10)
        self.cell(0, 7, str(value), new_x="LMARGIN", new_y="NEXT")

    def build(self, data: AcordFormData) -> AcordPDF:
        """Render the full form into the PDF."""
        self.add_page()
        self.alias_nb_pages()

        # Title
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 12, ACORD_TITLE, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

        # Thin separator line
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

        # Applicant section
        self._section_title("Applicant Information")
        self._field_row("Name", data.applicant_name)
        self._field_row("Address", data.applicant_address)
        self._field_row("Phone", data.applicant_phone)
        self._field_row("Email", data.applicant_email)
        self.ln(3)

        # Policy section
        self._section_title("Policy Information")
        self._field_row("Policy Number", data.policy_number)
        self._field_row("Effective Date", data.policy_effective_date)
        self._field_row("Expiry Date", data.policy_expiry_date)
        self.ln(3)

        # Vehicle section
        self._section_title("Vehicle Information")
        self._field_row("Year", str(data.vehicle_year))
        self._field_row("Make", data.vehicle_make)
        self._field_row("Model", data.vehicle_model)
        self._field_row("VIN", data.vehicle_vin)
        self._field_row("Color", data.vehicle_color)
        self.ln(3)

        # Loss section
        self._section_title("Loss Information")
        self._field_row("Loss Date", data.loss_date)
        self._field_row("Loss Time", data.loss_time)
        self._field_row("Loss Location", data.loss_location)
        self._field_row("Description", data.loss_description)
        self._field_row("Est. Repair Amount", _currency(data.estimated_repair_amount))
        self._field_row("Coverage Type", data.coverage_type)
        self.ln(3)

        # Claimant section
        self._section_title("Claimant Contact")
        self._field_row("Name", data.claimant_name)
        self._field_row("Phone", data.claimant_phone)
        self._field_row("Email", data.claimant_email)

        return self


def render_pdf(data: AcordFormData, path: Path) -> Path:
    """Render form data to a PDF file and return the path."""
    pdf = AcordPDF()
    pdf.build(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(path))
    return path


# ---------------------------------------------------------------------------
# Ground-truth JSON
# ---------------------------------------------------------------------------


def write_ground_truth(data: AcordFormData, path: Path) -> Path:
    """Write the ground-truth JSON for a single form."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data.to_dict(), indent=2) + "\n")
    return path


# ---------------------------------------------------------------------------
# Azure DI training sample
# ---------------------------------------------------------------------------

# Approximate y-positions for each section/field group in the PDF layout.
# These are used to construct plausible bounding boxes for the training labels.
_FIELD_Y_MAP: list[tuple[str, str]] = [
    ("applicant_name", "Applicant Name"),
    ("applicant_address", "Applicant Address"),
    ("applicant_phone", "Applicant Phone"),
    ("applicant_email", "Applicant Email"),
    ("policy_number", "Policy Number"),
    ("policy_effective_date", "Policy Effective Date"),
    ("policy_expiry_date", "Policy Expiry Date"),
    ("vehicle_year", "Vehicle Year"),
    ("vehicle_make", "Vehicle Make"),
    ("vehicle_model", "Vehicle Model"),
    ("vehicle_vin", "Vehicle VIN"),
    ("vehicle_color", "Vehicle Color"),
    ("loss_date", "Loss Date"),
    ("loss_time", "Loss Time"),
    ("loss_location", "Loss Location"),
    ("loss_description", "Loss Description"),
    ("estimated_repair_amount_formatted", "Est. Repair Amount"),
    ("coverage_type", "Coverage Type"),
    ("claimant_name", "Claimant Name"),
    ("claimant_phone", "Claimant Phone"),
    ("claimant_email", "Claimant Email"),
]


def _make_bounding_box(index: int, text: str) -> dict[str, list[list[float]]]:
    """Create a plausible bounding box for a field at the given row index."""
    # Each row is ~7pt tall, starting after the title (~y=30).
    # Label is in the first 60mm, value starts at 60mm.
    y_top = 30.0 + index * 10.0
    y_bottom = y_top + 7.0
    x_left = 70.0
    # Width varies with text length (approx 2mm per char).
    x_right = x_left + max(30.0, len(text) * 2.0)
    # Normalize to 0-1 range assuming A4: 210mm x 297mm
    return {
        "boundingBox": [
            [round(x_left / 210, 4), round(y_top / 297, 4)],
            [round(x_right / 210, 4), round(y_top / 297, 4)],
            [round(x_right / 210, 4), round(y_bottom / 297, 4)],
            [round(x_left / 210, 4), round(y_bottom / 297, 4)],
        ]
    }


def write_training_sample(data: AcordFormData, sample_dir: Path, filename: str) -> Path:
    """Write an Azure DI training sample (PDF + ocr.json + labels.json) into sample_dir."""
    sample_dir.mkdir(parents=True, exist_ok=True)

    # Copy the PDF into the sample folder
    pdf_path = sample_dir / filename
    render_pdf(data, pdf_path)

    # ocr.json — minimal valid structure expected by Azure DI labeling tools.
    ocr: dict[str, Any] = {
        "status": "succeeded",
        "createdDateTime": datetime.utcnow().isoformat() + "Z",
        "lastUpdatedDateTime": datetime.utcnow().isoformat() + "Z",
        "analyzeResult": {
            "version": "3.1",
            "modelId": "prebuilt-document",
            "pages": [
                {
                    "page": 1,
                    "angle": 0,
                    "width": 210,
                    "height": 297,
                    "unit": "millimeter",
                    "lines": [],
                }
            ],
        },
    }

    # Build lines in OCR for each field value
    d = data.to_dict()
    lines: list[dict[str, Any]] = []
    for idx, (field_key, _label_text) in enumerate(_FIELD_Y_MAP):
        text_value = str(d.get(field_key, ""))
        y_top = 30.0 + idx * 10.0
        lines.append(
            {
                "text": text_value,
                "boundingBox": [
                    70.0,
                    y_top,
                    70.0 + max(30, len(text_value) * 2),
                    y_top,
                    70.0 + max(30, len(text_value) * 2),
                    y_top + 7.0,
                    70.0,
                    y_top + 7.0,
                ],
                "words": [
                    {
                        "text": text_value,
                        "boundingBox": [
                            70.0,
                            y_top,
                            70.0 + max(30, len(text_value) * 2),
                            y_top,
                            70.0 + max(30, len(text_value) * 2),
                            y_top + 7.0,
                            70.0,
                            y_top + 7.0,
                        ],
                    }
                ],
            }
        )
    ocr["analyzeResult"]["pages"][0]["lines"] = lines

    ocr_path = sample_dir / "ocr.json"
    ocr_path.write_text(json.dumps(ocr, indent=2) + "\n")

    # labels.json — field-name to text mappings with bounding boxes.
    labels_list: list[dict[str, Any]] = []
    for idx, (field_key, _label_text) in enumerate(_FIELD_Y_MAP):
        text_value = str(d.get(field_key, ""))
        labels_list.append(
            {
                "label": field_key,
                "value": [
                    {
                        "text": text_value,
                        **_make_bounding_box(idx, text_value),
                    }
                ],
            }
        )

    labels_data = {
        "document": filename,
        "labels": labels_list,
    }
    labels_path = sample_dir / "labels.json"
    labels_path.write_text(json.dumps(labels_data, indent=2) + "\n")

    return sample_dir


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(
    count: int = 50,
    training_count: int = 20,
    seed: int = 42,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Generate the full ACORD synthetic dataset.

    Parameters
    ----------
    count : int
        Number of PDF forms + ground-truth JSON pairs to generate.
    training_count : int
        Number of Azure DI training samples (subset of *count*).
    seed : int
        Random seed for deterministic output.
    base_dir : Path | None
        Root directory for output. Defaults to ``evaluation/datasets/acord_synthetic``
        relative to this file's parent.

    Returns
    -------
    dict with summary statistics.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent / "datasets" / "acord_synthetic"

    rng = random.Random(seed)

    forms_dir = base_dir / "forms"
    labels_dir = base_dir / "labels"
    training_dir = base_dir / "training"

    # Generate all form data records
    all_data = [generate_form_data(rng) for _ in range(count)]

    # Write PDF forms and ground-truth JSON
    for i, data in enumerate(all_data):
        prefix = f"acord_{i + 1:04d}"
        render_pdf(data, forms_dir / f"{prefix}.pdf")
        write_ground_truth(data, labels_dir / f"{prefix}.json")

    # Write training samples (first training_count forms)
    actual_training = min(training_count, count)
    for i in range(actual_training):
        prefix = f"acord_{i + 1:04d}"
        sample_dir = training_dir / prefix
        write_training_sample(all_data[i], sample_dir, f"{prefix}.pdf")

    summary = {
        "total_forms": count,
        "training_samples": actual_training,
        "seed": seed,
        "forms_dir": str(forms_dir),
        "labels_dir": str(labels_dir),
        "training_dir": str(training_dir),
    }
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic ACORD 1 form dataset for ClaimPilot",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=50,
        help="Number of PDF forms to generate (default: 50)",
    )
    parser.add_argument(
        "--training-count",
        type=int,
        default=20,
        help="Number of Azure DI training samples (default: 20)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic generation (default: 42)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    result = main(count=args.count, training_count=args.training_count, seed=args.seed)
    print(json.dumps(result, indent=2))
