# ACORD 1 Synthetic Dataset

Auto-generated synthetic ACORD 1 Personal Auto Application forms for ClaimPilot
evaluation and Azure Document Intelligence model training.

## Regeneration

```bash
# From the project root:
python -m evaluation.generate_acord_synthetic

# With custom parameters:
python -m evaluation.generate_acord_synthetic --count 100 --training-count 30 --seed 123
```

The default seed (42) produces deterministic output. Changing the seed changes
every generated form while keeping the same structure.

## Directory Structure

```
acord_synthetic/
  forms/            # Generated PDF forms (acord_0001.pdf .. acord_NNNN.pdf)
  labels/           # Ground-truth JSON   (acord_0001.json .. acord_NNNN.json)
  training/         # Azure DI training samples
    acord_0001/
      acord_0001.pdf
      ocr.json      # Minimal OCR result structure
      labels.json   # Field-name to bounding-box label mappings
    acord_0002/
      ...
  README.md
```

## Field Schema

Each ground-truth JSON file is a flat dictionary with these fields:

### Applicant Information

| Field                     | Type   | Example                         |
|---------------------------|--------|---------------------------------|
| `applicant_first_name`    | string | "James"                         |
| `applicant_last_name`     | string | "Smith"                         |
| `applicant_name`          | string | "James Smith" (computed)        |
| `applicant_street`        | string | "1234 Main St"                  |
| `applicant_city`          | string | "Springfield"                   |
| `applicant_state`         | string | "IL"                            |
| `applicant_zip`           | string | "62704"                         |
| `applicant_address`       | string | "1234 Main St, Springfield, ..."|
| `applicant_phone`         | string | "(217) 555-1234"                |
| `applicant_email`         | string | "james.smith@gmail.com"         |

### Policy Information

| Field                     | Type   | Example                         |
|---------------------------|--------|---------------------------------|
| `policy_number`           | string | "AB12345678" (2 letters + 8 digits) |
| `policy_effective_date`   | string | "2024-03-15" (ISO date)         |
| `policy_expiry_date`      | string | "2025-03-15" (ISO date)         |

### Vehicle Information

| Field                     | Type   | Example                         |
|---------------------------|--------|---------------------------------|
| `vehicle_year`            | int    | 2022                            |
| `vehicle_make`            | string | "Toyota"                        |
| `vehicle_model`           | string | "Camry"                         |
| `vehicle_vin`             | string | "1HGCM82633A004352" (17 chars)  |
| `vehicle_color`           | string | "Silver"                        |

### Loss Information

| Field                            | Type   | Example                                    |
|----------------------------------|--------|--------------------------------------------|
| `loss_date`                      | string | "2024-06-20" (ISO date)                    |
| `loss_time`                      | string | "14:30"                                    |
| `loss_location`                  | string | "Springfield, IL"                          |
| `loss_description`               | string | "Rear-end collision at stoplight..."       |
| `estimated_repair_amount`        | float  | 3750.00                                    |
| `estimated_repair_amount_formatted` | string | "$3,750.00" (computed)                  |
| `coverage_type`                  | string | "Collision"                                |

### Claimant Contact

| Field                     | Type   | Example                         |
|---------------------------|--------|---------------------------------|
| `claimant_first_name`     | string | "Patricia"                      |
| `claimant_last_name`      | string | "Johnson"                       |
| `claimant_name`           | string | "Patricia Johnson" (computed)   |
| `claimant_phone`          | string | "(312) 555-9876"                |
| `claimant_email`          | string | "patricia.johnson@yahoo.com"    |

## Training Samples

The `training/` subdirectory contains samples formatted for Azure Document
Intelligence custom model labeling. Each sample folder includes:

- The original PDF form
- `ocr.json` -- a minimal valid OCR result with page dimensions and text lines
- `labels.json` -- labeled field-to-region mappings with normalized bounding boxes

Bounding boxes are normalized to 0-1 range relative to the A4 page dimensions
(210mm x 297mm). Each label entry contains the field name, extracted text, and
a four-corner polygon.
