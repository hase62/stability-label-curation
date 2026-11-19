"""Task 2.41-B selection kernel from ba19137, independent of run state."""
from __future__ import annotations
from collections import Counter, defaultdict
from fractions import Fraction
import random

def stratum(row):return row['hla'],len(row['peptide'])


def select_exclusions(rows: list[dict], ranks: dict[str,Fraction], seeds: list[int]) -> tuple[dict,dict]:
    """R selection receives only eligible identities/strata and H's quotas, no scores."""
    if len({r['source_row_id'] for r in rows})!=len(rows):raise ValueError('Duplicate training identity')
    eligible=[r for r in rows if r['original_label']=='1' and r['source_row_id'] in ranks]
    groups=defaultdict(list)
    for r in eligible:groups[r['hla']].append(r)
    hard=[]
    for hla,group in sorted(groups.items()):
        hard.extend(r['source_row_id'] for r in sorted(group,key=lambda r:(ranks[r['source_row_id']],r['source_row_id']))[:len(group)//10])
    lookup={r['source_row_id']:r for r in rows};quota=Counter(stratum(lookup[i]) for i in hard)
    selections={'H':sorted(hard)}
    for i,seed in enumerate(seeds,1):selections[f'R{i}']=random_exclusions(eligible,quota,seed)
    original=Counter(stratum(r) for r in rows if r['original_label']=='1')
    for arm,ids in selections.items():
        if len(ids)!=len(set(ids)) or Counter(stratum(lookup[i]) for i in ids)!=quota:raise ValueError('Matched exclusion quota failed')
        if any(lookup[i]['original_label']!='1' or i not in ranks for i in ids):raise ValueError('Negative/missing-score exclusion prohibited')
        if any(original[s]-quota[s]<=0 for s in original):raise ValueError('An entire positive stratum disappears; stop without changing rule')
    return selections,{'eligible_positive':len(eligible),'missing_or_outside_positive':sum(r['original_label']=='1' for r in rows)-len(eligible),
        'excluded':len(hard),'excluded_fraction_of_all_positives':len(hard)/sum(r['original_label']=='1' for r in rows),
        'by_stratum':{f'{h}|{n}':{'original_positive':original[(h,n)],'excluded':quota[(h,n)],'remaining_positive':original[(h,n)]-quota[(h,n)]} for h,n in sorted(original)},
        'negative_excluded':0,'labels_changed':0,'rank_reference':'immutable unfiltered Task2.31 training positives','ranks_recomputed':False}


def random_exclusions(eligible: list[dict],quota: Counter,seed: int) -> list[str]:
    groups=defaultdict(list)
    for r in eligible:groups[stratum(r)].append(r['source_row_id'])
    rng=random.Random(seed);out=[]
    for s in sorted(groups):out.extend(rng.sample(sorted(groups[s]),quota[s]))
    return sorted(out)
