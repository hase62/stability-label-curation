#!/usr/bin/env python3
"""Explicitly separated Task 2.40 prediction and post-seal evaluation stages."""
import argparse


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','mix','spearmint','seal','evaluate','verify']);args=parser.parse_args()
    if args.stage in ('evaluate','verify'):
        from stability_label_curation import modern_frozen_evaluation as evaluation
        getattr(evaluation,args.stage)()
    else:
        from stability_label_curation import modern_frozen_scoring as scoring
        if args.stage in ('mix','spearmint'):scoring.predict(args.stage)
        else:getattr(scoring,args.stage)()


if __name__=='__main__':main()
