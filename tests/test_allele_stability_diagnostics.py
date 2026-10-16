"""Small frozen-score fixtures; no scientific payloads, prediction or training."""
from contextlib import redirect_stdout
from copy import deepcopy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import allele_stability_diagnostics as audit
from stability_label_curation import pseudolabel_pilot as pilot
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
from stability_label_curation.__main__ import main

HLA='HLA-B*08:01'
ABSENT='HLA-A*02:01'
UNSUPPORTED='HLA-B*35:08'


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths=resolve_paths({'CODEX_ROOT':self.temp.name});self.paths.project_data_dir.mkdir(parents=True)
        self.context=SimpleNamespace(archive_sha256='a'*64,model_sha256='b'*64,mapping={HLA:HLA},
            model=SimpleNamespace(document={'config':{},'alleles':{
                HLA:{'status':'trained'},ABSENT:{'status':'trained'},UNSUPPORTED:{'status':'insufficient_training_support'}}}))
        self.network=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network'))
        self.network.start();self.addCleanup(self.network.stop)

    def row(self,index=1,label='1',hours=0.5,exact=False,near=False,member='el_train.csv'):
        cat,action,proposed=pilot.category_and_action(label,hours)
        row={key:'0' for key in pilot.FIELDS}
        row.update(source_file=member,row_index=str(index),source_line_number=str(index+1),
            source_row_id=pilot.row_id(self.context.archive_sha256,member,index),source_row_sha256='c'*64,
            original_peptide='AAAAAAAAA',original_hla=HLA,resolved_hla=HLA,original_label=label,
            predicted_half_life_hours=str(hours),model_status='ok',teacher_version=pilot.teacher.VERSION,
            teacher_model_sha256=self.context.model_sha256,rule_version=pilot.VERSION,
            teacher_fit_exact_peptide=str(int(exact)),teacher_fit_within_one_mismatch_peptide=str(int(near or exact)),
            candidate_action=action,proposed_pseudolabel=proposed,stability_category=cat)
        return row

    def summarize(self,rows,minimum=1):
        return audit.summarize_scores(iter(rows),'el_train.csv',self.context,minimum)

    def test_exact_class_distributions(self):
        d,a,c=self.summarize([self.row(1,'1',0),self.row(2,'1',2),self.row(3,'0',10)])
        self.assertEqual(c['labels'],{'1':2,'0':1})
        self.assertEqual(d[HLA]['1']['quantiles_hours']['p50'],1)
        self.assertEqual(d[HLA]['1']['IQR_hours'],1)
        self.assertEqual(a[HLA]['all']['ROC_AUC'],0)

    def test_quantiles_and_empty_classes(self):
        self.assertEqual(audit.quantile([0,10],5),0.5)
        self.assertEqual(audit.quantile([7],95),7)
        self.assertIsNone(audit.quantile([],50))
        with self.assertRaises(ValueError):audit.quantile([0],101)
        d,_,_=self.summarize([])
        self.assertEqual(d[ABSENT]['1']['n'],0)
        self.assertIsNone(d[ABSENT]['1']['historical_LOW_lt1_fraction'])

    def test_historical_boundary_definitions(self):
        d=audit.describe([0,1,10,11])
        self.assertEqual(d['historical_LOW_lt1_fraction'],0.25)
        self.assertEqual(d['historical_HIGH_ge10_fraction'],0.5)
        self.assertEqual(d['strictly_gt10_fraction'],0.25)

    def test_roc_auc_perfect_reversed_and_ties(self):
        self.assertEqual(audit.roc_auc([3,4],[1,2],1)['ROC_AUC'],1)
        self.assertEqual(audit.roc_auc([1,2],[3,4],1)['ROC_AUC'],0)
        self.assertEqual(audit.roc_auc([1,1],[1,1],1)['ROC_AUC'],0.5)
        self.assertEqual(audit.roc_auc([1,2],[1,2],1)['ROC_AUC'],0.5)
        self.assertEqual(audit.roc_auc([0,1,1],[0,1,2],1)['ROC_AUC'],3.5/9)

    def test_auc_matches_pairwise_reference(self):
        positives=[0,0,1,2,2,4];negatives=[0,1,1,2,3]
        expected=sum((p>n)+0.5*(p==n) for p in positives for n in negatives)/(len(positives)*len(negatives))
        self.assertAlmostEqual(audit.roc_auc(positives,negatives,1)['ROC_AUC'],expected)

    def test_auc_unavailable_support(self):
        self.assertEqual(audit.roc_auc([1],[],1)['status'],'missing_class')
        self.assertEqual(audit.roc_auc([1],[2],5)['status'],'insufficient_class_support')
        self.assertIsNone(audit.roc_auc([1],[2],5)['ROC_AUC'])
        with self.assertRaises(ValueError):audit.roc_auc([float('nan')],[1],1)

    def test_exposure_strata(self):
        rows=[self.row(1,exact=True),self.row(2,near=True),self.row(3)]
        _,a,_=self.summarize(rows)
        for s in audit.STRATA[1:]:self.assertEqual(a[HLA][s]['positive_rows'],1)
        self.assertEqual(a[HLA]['all']['positive_rows'],3)

    def test_unsupported_HLA_rejected_without_mapping(self):
        row=self.row();row['resolved_hla']=UNSUPPORTED
        with self.assertRaises(ValueError):self.summarize([row])
        self.assertNotIn(UNSUPPORTED,audit.supported_alleles(self.context))

    def test_fuzzy_allele_mapping_not_allowed(self):
        row=self.row();row['original_hla']='HLA-B*08:99'
        with self.assertRaises(ValueError):self.summarize([row])

    def test_mutant_not_accepted(self):
        row=self.row();row['original_hla']=HLA+'(C67S)'
        with self.assertRaises(ValueError):self.summarize([row])

    def test_bad_model_source_or_coordinate_rejected(self):
        for key,value in [('source_file','im_val.csv'),('teacher_model_sha256','f'*64),('source_row_id','invented'),('rule_version','new')]:
            row=self.row();row[key]=value
            with self.assertRaises(ValueError):self.summarize([row])

    def test_nonfinite_negative_and_invalid_label(self):
        for key,value in [('predicted_half_life_hours','inf'),('predicted_half_life_hours','-1'),('original_label','2')]:
            row=self.row();row[key]=value
            with self.assertRaises(ValueError):self.summarize([row])

    def test_inconsistent_exposure_rejected(self):
        row=self.row(exact=True);row['teacher_fit_within_one_mismatch_peptide']='0'
        with self.assertRaises(ValueError):self.summarize([row])

    def test_changed_historical_action_rejected(self):
        row=self.row();row['candidate_action']='no_change'
        with self.assertRaises(ValueError):self.summarize([row])

    def test_duplicate_score_indices_rejected(self):
        with self.assertRaises(ValueError):self.summarize([self.row(),self.row()])

    def test_sealed_or_validation_scores_forbidden(self):
        for member in ('el_test.csv','im_test.csv','im_val.csv','iedb.csv'):
            with self.assertRaises(ValueError):audit.summarize_scores([],member,self.context)

    def test_source_rows_and_labels_unchanged(self):
        rows=[self.row(),self.row(2,'0',10)];original=deepcopy(rows)
        self.summarize(rows)
        self.assertEqual(rows,original)

    def test_corrected_views_marked_unapproved(self):
        group={'teacher_eligible_rows':3,'eligible_original_label_counts':{'1':2,'0':1},
            'candidate_counts':{'low_positive_to_negative':2,'high_negative_to_positive':1}}
        summary={'members':{m:{'by_original_HLA':{HLA:group}} for m in pilot.MEMBERS}}
        retained={HLA:{'original':{'1':1,'0':1},'actions':{'low_positive_to_negative':1},'low_and_high':{'0':2}}}
        inventory={m:{'by_HLA':retained} for m in pilot.MEMBERS}
        experiment={'artifacts':{'processed/el_train_low_and_high.csv':{'sha256':'a'*64,'bytes':3},
                                 'processed/el_train_original.csv':{'sha256':'b'*64,'bytes':3}}}
        result=audit.correction_shifts(summary,inventory,experiment)
        self.assertEqual(result['training_use_status'],audit.STATUS)
        self.assertEqual(len(result['historical_corrected_views']),1)
        self.assertTrue(result['by_member']['el_train.csv']['Task25_retained_population'][HLA]['all_original_positives_changed'])
        self.assertEqual(inventory['el_train.csv']['by_HLA'][HLA]['original']['1'],1)

    def test_shift_count_integrity(self):
        with self.assertRaises(ValueError):audit._shift({'1':1,'0':1},2,0)

    def test_no_strategy_or_cutoff_selected(self):
        result=audit.strategy_assessment()
        self.assertIsNone(result['selected_method']);self.assertIsNone(result['selected_cutoff'])
        self.assertEqual(result['training_use_status'],audit.STATUS)

    def test_dtu_decimal_and_saved_validation_metrics(self):
        population=[SimpleNamespace(original_allele=HLA,original_measurement_text=v,observation_id=str(i)) for i,v in enumerate(['0.00','0.10','0.30'])]
        metrics={'results':{HLA:{'teacher':{'n':2,'spearman_hours':None,'mae_hours':0.2}}}}
        partition={'assignments':[{'observation_id':str(i),'partition':'train' if i<2 else 'validation'} for i in range(3)]}
        d=audit.dtu_context(population,self.context,metrics,partition)
        self.assertEqual(d['by_HLA'][HLA]['reported_zero_count'],1)
        self.assertEqual(d['by_HLA'][HLA]['measured_quantiles_hours_decimal']['p50'],'0.10')
        self.assertTrue(d['by_HLA'][HLA]['validation_sparse_below10'])
        self.assertEqual(d['by_HLA'][ABSENT]['saved_validation_n'],0)

    def test_checksum_gate_and_path_safety(self):
        c=audit.load_config(self.paths.repository_root/audit.CONFIG)
        f=self.paths.project_data_dir/'tampered';f.write_text('tampered')
        overrides={k:f for k in c['inputs']}
        with self.assertRaises(ValueError):audit.resolve_inputs(c,self.paths,overrides)
        c['inputs']['teacher']['relative_path']='../escape'
        target=self.paths.project_data_dir/'config.json';target.write_text(raw.json_report(c))
        with self.assertRaises(ValueError):audit.load_config(target)

    def test_status_cannot_be_approved_by_configuration(self):
        c=audit.load_config(self.paths.repository_root/audit.CONFIG);c['corrected_training_status']='approved'
        f=self.paths.project_data_dir/'bad.json';f.write_text(raw.json_report(c))
        with self.assertRaises(ValueError):audit.load_config(f)

    def test_deterministic_json(self):
        rows=[self.row(),self.row(2,'0',10)]
        self.assertEqual(raw.json_report(self.summarize(rows)),raw.json_report(self.summarize(deepcopy(rows))))

    def test_readonly_default_and_cli_compatibility(self):
        expected={'only':'aggregate data'}
        with patch.object(audit,'inspect',return_value=(expected,[],{})),patch.object(raw,'write_report',side_effect=AssertionError('Write forbidden')):
            self.assertEqual(audit.execute(config_path='unused',paths=self.paths),expected)
            with redirect_stdout(io.StringIO()):self.assertEqual(main(['allele-diagnostics'],env={'CODEX_ROOT':self.temp.name}),0)
        for command in ('allele-diagnostics','pilot-prepare','teacher','pseudolabel'):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as e:main([command,'--help'])
            self.assertEqual(e.exception.code,0)

    def test_report_write_readonly_replay_and_mismatch(self):
        source=self.paths.project_data_dir/'frozen.txt';source.write_text('unchanged')
        config=self.paths.project_data_dir/'config.json';config.write_text('{}')
        inputs=[{'path':str(source),'sha256':raw.sha256_file(source)}]
        run=runs.create_run(paths=self.paths,kind='test',config=config,inputs=[source],argv=['synthetic diagnostic'],allow_dirty=True)
        reports={'test_aggregate.json':{'original_labels_preserved':True,'training_status':audit.STATUS}}
        with patch.object(audit,'inspect',return_value=(reports,inputs,{'Teacher_refitted_or_rescored':False})):
            audit.execute(config_path=config,out=run,paths=self.paths)
            original=raw.sha256_file(run/'reports/test_aggregate.json')
            with patch.object(raw,'write_report',side_effect=AssertionError('Read-only replay')):
                audit.execute(config_path=config,out=run,paths=self.paths,verify_existing=True)
            self.assertEqual(original,raw.sha256_file(run/'reports/test_aggregate.json'))
            self.assertEqual(source.read_text(),'unchanged')
            (run/'reports/test_aggregate.json').write_text('{}')
            with self.assertRaises(ValueError):audit.execute(config_path=config,out=run,paths=self.paths,verify_existing=True)

    def test_replay_needs_explicit_run(self):
        with self.assertRaises(ValueError):audit.execute(config_path='unused',paths=self.paths,verify_existing=True)

    def test_source_file_checksum_pass_then_tamper(self):
        config=audit.load_config(self.paths.repository_root/audit.CONFIG)
        target=self.paths.project_data_dir/'identity';target.write_text('frozen')
        sha=raw.sha256_file(target)
        for key in config['inputs']:config['inputs'][key]={'area':'data','relative_path':target.name,'sha256':sha}
        resolved,identities=audit.resolve_inputs(config,self.paths)
        self.assertEqual(len(resolved),16)
        target.write_text('changed')
        with self.assertRaises(ValueError):audit.resolve_inputs(config,self.paths)
