# ClaimPilot Architecture

This directory contains architecture diagram sources for ClaimPilot.

## Live Azure Architecture

The README image is generated with [`mingrammer/diagrams`](https://github.com/mingrammer/diagrams):

```bash
pip install "diagrams>=0.25.0"
python docs/architecture/claimpilot_live_architecture.py
```

Outputs:

- `claimpilot_live_architecture.py` — Python diagram-as-code source.
- `claimpilot_live_architecture.png` — rendered image referenced by `README.md`.

## Legacy Mermaid Diagram

```bash
# Using mermaid-cli (npm install -g @mermaid-js/mermaid-cli)
mmdc -i claimpilot-architecture.mmd -o claimpilot-architecture.png

# Or using the Mermaid Live Editor: https://mermaid.live
```

## Diagram Source

See `claimpilot-architecture.mmd` for the Mermaid source.
