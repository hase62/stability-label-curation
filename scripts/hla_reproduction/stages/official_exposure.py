"""Read-only public-source exposure and frozen population metadata; no predictors."""
from common import *
from prepare import raw_path
import zipfile

def main():
 commands();validate_seal(training=True);archive=raw_path('bigmhc_v4');expected='0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa';assert sha(archive)==expected
 cohorts={n:records(D/'cohorts'/f'{n}_identities.jsonl') for n in ['IMPROVE','Neo']};wanted={r['peptide'] for rr in cohorts.values() for r in rr};counts=[];acquisition=[]
 with zipfile.ZipFile(archive) as z:
  for member in ['el_train.csv','el_val.csv','el_test.csv','im_train.csv','im_val.csv','im_test.csv']:
   exact=set();pairs=set();n=0;hlacount=Counter()
   with z.open(member) as b,io.TextIOWrapper(b,encoding='utf-8-sig',newline='') as f:
    reader=csv.reader(f);header=next(reader);assert header[:3]==['mhc','pep','tgt']
    for row in reader:
     n+=1;h=runner.data.canonical_hla(row[0]);p=row[1].strip().upper();hlacount[h]+=1
     if p in wanted:exact.add(p);pairs.add((p,h))
   for name,rr in cohorts.items():counts.append({'cohort':name,'public_dataset':member,'source_split':member.split('_',1)[1].removesuffix('.csv'),'source_training_modality':'EL' if member.startswith('el') else 'IM','published_source_rows':n,'cohort_n':len(rr),'exact_peptide_observations':sum(r['peptide'] in exact for r in rr),'exact_pair_observations':sum((r['peptide'],r['hla']) in pairs for r in rr),'source_HLA_overlap':len({r['hla'] for r in rr}&set(hlacount)),'weight_training_correspondence':'Published BigMHC v4 data; complete per-weight membership and2023 byte identity NOT_ESTABLISHED','interpretation':'Published validation/test identities distinguished from training; match is not proof of IM-label leakage'})
   acquisition.append({'logical_source':'Mendeley BigMHC v4 datasets.zip::'+member,'rows':n,'raw_archive_SHA256':expected,'schema_first3':header[:3],'raw_member_bytes':z.getinfo(member).file_size})
 csvout(D/'metrics/OFFICIAL_PUBLIC_DATA_EXPOSURE.csv',counts);put(D/'preflight/OFFICIAL_DATA_SOURCE_RECEIPT.json',{'status':'LOCAL_AUTHENTICATED_PUBLIC_SOURCE','archive_reference':'data/bigmhc_v4/datasets.zip','archive_SHA256':expected,'DOI':'10.17632/dvmz6pkzvb.4','sources':acquisition,'checkpoint_membership_claim':'not fully established for each ensemble member','no_external_model_fitting':True})

if __name__ == '__main__':
    main()
