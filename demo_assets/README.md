# Demo Assets — ClaimPilot

Three deterministic synthetic claim bundles for manual frontend testing and live Azure validation. **No PII — all data is fictional.**

## Generating the Bundles

```bash
python scripts/generate_demo_assets.py
```

This creates `demo_assets/` with three claim folders. Re-running produces identical output.

## Claim Bundles

| Bundle | Claimant | Policy # | Expected Outcome | Scenario |
|---|---|---|---|---|
| `claim_001_approve` | Maria Thompson | AT42093871 | APPROVED | Minor front bumper/hood damage from deer collision |
| `claim_002_escalate` | James Chen | JC77120456 | ESCALATED | Rear-end collision with $18,750 repair estimate |
| `claim_003_fraud_review` | Diana Brooks | DB55309128 | FRAUD_REVIEW | Hit-and-run with inconsistent damage description |

## Files per Bundle

Each claim folder contains:

| File | Description |
|---|---|
| `metadata.json` | Claimant name, policy number, scenario description, expected outcome |
| `claim_form.pdf` | ACORD-like claim form with matching data |
| `photo_1.jpg` | Placeholder damage photo (synthetic colored rectangle) |
| `photo_2.jpg` | Placeholder damage photo (synthetic colored rectangle) |
| `voice_statement.txt` | Transcript of the claimant's voice statement |

Audio files are **not included** — the voice transcript can be used directly as a text statement.

## Using with the Frontend

Open the ClaimPilot upload form and for a given claim:

1. **Claim Form** field: select `claim_form.pdf`
2. **Photos** field: select both `photo_1.jpg` and `photo_2.jpg`
3. **Voice Statement** field: either upload an audio file (optional) or paste the contents of `voice_statement.txt`
4. Submit and observe the pipeline progress
