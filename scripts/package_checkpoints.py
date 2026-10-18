#!/usr/bin/env python3
"""Run manifest-selected checkpoint packaging from a checkout without installation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from stability_label_curation.checkpoint_package import main

if __name__ == '__main__':
    raise SystemExit(main())
