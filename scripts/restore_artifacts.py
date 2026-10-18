#!/usr/bin/env python3
"""Run the repository-controlled restorer from a fresh checkout, without install."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from stability_label_curation.artifact_restore import main

if __name__=='__main__':
    raise SystemExit(main())
