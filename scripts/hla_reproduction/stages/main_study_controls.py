"""Exact positive-row controls for the planned EL20 -> IM30 study.

This prepares weights only; it does not train, infer, access IM labels, or
modify the historical ledger. Row-level outputs belong in a PRIVATE run dir.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, random, struct
from fractions import Fraction
from pathlib import Path

ARMS=('A','W_two','L','W_two_perm','L_perm','L_const')
NAMESPACE='HLA_MAIN_EL20_IM30_CONTROL_V1'
def f32(x):return struct.unpack('f',struct.pack('f',float(x)))[0]
def weight(r):return Fraction(1)+Fraction(1,2)*(r-Fraction(1,2))
def prepare(rows,seed):
    groups=collections.defaultdict(list);ids=set()
    for row in rows:
        sid=row['source_row_id']
        if sid in ids:raise ValueError('Duplicate source_row_id')
        ids.add(sid);r=Fraction(row['rank_exact'])
        if not 0<=r<=1:raise ValueError('Invalid rank')
        w=weight(r);l=min(Fraction(1),w)
        if Fraction(row['W_exact'])!=w or Fraction(row['L_exact'])!=l:raise ValueError('Historical formula mismatch')
        if 'W_FP32' in row and f32(w)!=float(row['W_FP32']):raise ValueError('Historical W FP32 mismatch')
        if 'L_FP32' in row and f32(l)!=float(row['L_FP32']):raise ValueError('Historical L FP32 mismatch')
        groups[row['hla']].append((sid,r))
    outputs=[];audit=[]
    for hla,g in sorted(groups.items()):
        g.sort(key=lambda x:x[0]);ranks=[x[1] for x in g]
        if sum(ranks)!=Fraction(len(g),2):raise ValueError('Ranks are not an exhaustive original within-HLA midrank population')
        perm_seed=int.from_bytes(hashlib.sha256(f'{NAMESPACE}|{seed}|{hla}'.encode()).digest(),'big')
        perm=list(ranks);random.Random(perm_seed).shuffle(perm)
        const=sum(min(Fraction(1),weight(x)) for x in ranks)/len(ranks)
        assert collections.Counter(ranks)==collections.Counter(perm)
        for (sid,r),pr in zip(g,perm):
            exact={'A':Fraction(1),'W_two':weight(r),'L':min(Fraction(1),weight(r)),'W_two_perm':weight(pr),'L_perm':min(Fraction(1),weight(pr)),'L_const':const}
            rec={'source_row_id':sid,'hla':hla,'training_seed':seed,'original_rank_exact':str(r),'permuted_rank_exact':str(pr)}
            for arm in ARMS:rec[arm+'_exact']=str(exact[arm]);rec[arm+'_FP32']=f32(exact[arm])
            outputs.append(rec)
        w0=[weight(x) for x in ranks];wp=[weight(x) for x in perm];l0=[min(Fraction(1),x) for x in w0];lp=[min(Fraction(1),x) for x in wp]
        assert collections.Counter(w0)==collections.Counter(wp) and collections.Counter(l0)==collections.Counter(lp)
        assert sum(w0)==len(g) and const*len(g)==sum(l0)
        audit.append({'hla':hla,'positive_n':len(g),'unique_original_rank_values':len(set(ranks)),'rank_values_changed_n':sum(x!=y for x,y in zip(ranks,perm)),'W_two_mean_exact':str(sum(w0)/len(g)),'L_mean_exact':str(const),'L_const_FP32':f32(const),'permutation_seed_hex':f'{perm_seed:064x}','rank_and_weight_multisets_preserved':True,'HLA_L_sum_exactly_matched_by_constant':True,'permutation_scope':'EL-positive rows within HLA; fixed across epochs; same permutation for W_two/L'})
    outputs.sort(key=lambda x:x['source_row_id'])
    return outputs,audit

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ledger',type=Path,required=True);p.add_argument('--private-output-dir',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True);p.add_argument('--expected-rows',type=int,default=63053);p.add_argument('--expected-hla',type=int,default=49)
    args=p.parse_args();raw=args.ledger.read_bytes();actual=hashlib.sha256(raw).hexdigest()
    if actual!=args.expected_sha256:raise ValueError('Input byte hash mismatch')
    opener=gzip.open if args.ledger.suffix=='.gz' else open
    with opener(args.ledger,'rt',encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=args.expected_rows or len({x['hla'] for x in rows})!=args.expected_hla:raise ValueError('Wrong positive-row population')
    args.private_output_dir.mkdir(parents=True,exist_ok=False)
    summaries=[]
    for seed in (42,123,456):
        out,audit=prepare(rows,seed)
        path=args.private_output_dir/f'positive_control_weights_seed{seed}.csv.gz'
        with path.open('xb') as rawout:
            with gzip.GzipFile(filename='',fileobj=rawout,mode='wb',mtime=0) as gz:
                import io
                with io.TextIOWrapper(gz,encoding='utf-8',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
        summaries.append({'seed':seed,'rows':len(out),'groups':audit,'row_output_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    document={'input_sha256':actual,'namespace':NAMESPACE,'planned_arms':ARMS,'input_population':'original EL-training positives only','negative_EL_weight':1,'IM_loss_weighting':'unweighted for every arm','outputs_are_PRIVATE':True,'seed_diagnostics':summaries,'execution':'WEIGHT_PREPARATION_ONLY_NO_TRAINING'}
    (args.private_output_dir/'control_preparation_audit.json').write_text(json.dumps(document,indent=2)+'\n')
    print(json.dumps({'status':'WEIGHTS_PREPARED_NOT_TRAINED','seeds':[42,123,456],'positive_rows':len(rows),'HLA_groups':args.expected_hla,'output_directory':str(args.private_output_dir)},indent=2))
if __name__=='__main__':main()
