"""Synthetic row provenance and descriptive inference boundaries; no network/ML fitting."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation import el_positive_stability_analysis as audit
from stability_label_curation import pseudolabel_pilot as pilot
from stability_label_curation import netmhcstabpan_2016 as raw
from stability_label_curation.paths import resolve_paths

HLA='HLA-B*08:01'


class ELHypothesisTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.paths=resolve_paths({'CODEX_ROOT':self.temp.name});self.root=Path(self.temp.name).resolve()
        self.context=SimpleNamespace(archive_sha256='a'*64,model_sha256='b'*64,mapping={HLA:HLA},
            model=SimpleNamespace(document={'config':{},'alleles':{HLA:{'status':'trained'}}}))
        net=patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('No network'))
        net.start();self.addCleanup(net.stop)

    def score(self,index=1,label='1',value='0.5',peptide='AAAAAAAAA'):
        return {'source_file':'el_train.csv','row_index':str(index),'source_line_number':str(index+1),
            'source_row_id':pilot.row_id('a'*64,'el_train.csv',index),
            'source_row_sha256':audit.adapter.source_hash(['mhc','pep','tgt'],[HLA,peptide,label]),
            'original_peptide':peptide,'original_hla':HLA,'resolved_hla':HLA,'original_label':label,
            'predicted_half_life_hours':value,'teacher_model_sha256':'b'*64,'teacher_version':audit.teacher.VERSION,
            'model_status':'ok',**{k:'0' for k in pilot.EXPOSURES}}

    def ledger(self,score,derived=1,retained=True):
        return {**{k:score[k] for k in audit.JOIN_FIELDS},'retained':'1' if retained else '0',
            'derived_row_index':str(derived) if retained else '',
            'exclusion_reason':'' if retained else 'development_one_mismatch_peptide'}

    def align(self,scores,ledgers,originals):
        result={};rows=list(audit.aligned_scores(scores,ledgers,originals,self.context,result));return rows,result

    def test_exact_provenance_join_and_55_style_reconciliation(self):
        scores=[self.score(1),self.score(2,'0',peptide='CAAAAAAAA')]
        ledgers=[self.ledger(scores[0]),self.ledger(scores[1],retained=False)]
        before=deepcopy(scores)
        rows,result=self.align(scores,ledgers,[[HLA,'AAAAAAAAA','1']])
        self.assertEqual(rows,[scores[0]]);self.assertEqual(result['pre_purge_rows'],2)
        self.assertEqual(result['retained_labels'],{'1':1});self.assertEqual(result['removed_labels'],{'0':1})
        self.assertEqual(result['labels_changed'],0);self.assertEqual(before,scores)

    def test_same_peptide_pair_does_not_replace_row_identity(self):
        score=self.score(1);ledger=self.ledger(self.score(2))
        with self.assertRaises(ValueError):self.align([score],[ledger],[[HLA,'AAAAAAAAA','1']])

    def test_changed_original_label_rejected(self):
        score=self.score()
        with self.assertRaises(ValueError):self.align([score],[self.ledger(score)],[[HLA,'AAAAAAAAA','0']])

    def test_changed_original_hash_rejected(self):
        score=self.score();score['source_row_sha256']='f'*64
        with self.assertRaises(ValueError):self.align([score],[self.ledger(score)],[[HLA,'AAAAAAAAA','1']])

    def test_duplicate_source_or_derived_identity_rejected(self):
        score=self.score()
        with self.assertRaises(ValueError):self.align([score,score],[self.ledger(score),self.ledger(score,2)],[[HLA,'AAAAAAAAA','1']]*2)
        second=self.score(2)
        with self.assertRaises(ValueError):self.align([score,second],[self.ledger(score),self.ledger(second,1)],[[HLA,'AAAAAAAAA','1']]*2)

    def test_missing_extra_original_or_score_rows_rejected(self):
        score=self.score()
        for scores,ledgers,originals in [([score],[],[]),([],[self.ledger(score)],[]),
                                        ([score],[self.ledger(score)],[]),([],[],[[HLA,'AAAAAAAAA','1']])]:
            with self.assertRaises(ValueError):self.align(scores,ledgers,originals)

    def test_nonfinite_negative_score_rejected(self):
        for value in ('NaN','Infinity','-0.1'):
            score=self.score(value=value)
            with self.assertRaises(ValueError):self.align([score],[self.ledger(score)],[[HLA,'AAAAAAAAA','1']])

    def test_unknown_hla_or_mhc_alias_rejected(self):
        score=self.score();score['resolved_hla']='HLA-B*08:02'
        with self.assertRaises(ValueError):self.align([score],[self.ledger(score)],[[HLA,'AAAAAAAAA','1']])
        self.context.model.document['alleles'][HLA]['status']='insufficient_training_support'
        score=self.score()
        with self.assertRaises(ValueError):self.align([score],[self.ledger(score)],[[HLA,'AAAAAAAAA','1']])

    def test_zero_is_preserved_not_synthetic_or_mislabeled(self):
        score=self.score(value='0.0')
        result=audit.summarize([score],[HLA])
        self.assertEqual(score['original_label'],'1');self.assertEqual(score['predicted_half_life_hours'],'0.0')
        self.assertEqual(result['positive']['overall']['predicted_zero_count'],1)
        self.assertNotIn('corrected_label',result['positive'])

    def test_quantiles_and_historical_boundaries_are_descriptive(self):
        result=audit.describe([0,1,2,3])
        self.assertEqual(result['quantiles_hours']['p50'],1.5);self.assertEqual(result['IQR_hours'],1.5)
        self.assertEqual(result['historical_lt1_count'],1)
        self.assertEqual(audit.describe([9.9,10,11])['historical_ge10_count'],2)
        self.assertEqual(sum(result['descriptive_bin_counts'].values()),4)
        self.assertIsNone(audit.describe([])['quantiles_hours']['p50'])

    def test_positive_first_class_and_hla_separation(self):
        scores=[self.score(1,'1','0.2'),self.score(2,'0','20',peptide='CAAAAAAAA')]
        r=audit.summarize(scores,[HLA,'HLA-A*02:01'])
        self.assertEqual(r['positive']['overall']['n'],1)
        self.assertEqual(r['positive']['by_HLA'][HLA]['quantiles_hours']['p50'],.2)
        self.assertEqual(r['secondary_negative']['overall']['n'],1)
        self.assertEqual(r['positive']['by_HLA']['HLA-A*02:01']['n'],0)

    def test_duplicate_and_conflicting_keys_are_not_assay_replicates(self):
        r=audit.summarize([self.score(1),self.score(2,'0'),self.score(3)],[HLA])
        self.assertEqual(r['duplicates']['duplicate_pair_groups'],1)
        self.assertEqual(r['duplicates']['extra_pair_records'],2)
        self.assertEqual(r['duplicates']['conflicting_label_keys'],1)
        self.assertIn('not verified assay replicates',r['duplicates']['interpretation'])

    def test_fitting_exposure_strata_and_association_are_not_validation(self):
        scores=[self.score(i+1,str(i%2),str(i)) for i in range(12)]
        scores[0]['teacher_fit_exact_peptide']='1';scores[0]['teacher_fit_within_one_mismatch_peptide']='1'
        r=audit.summarize(scores,[HLA])
        self.assertEqual(r['fitting_exposure']['0']['teacher_fit_exact_peptide'],1)
        self.assertEqual(r['comparison'][HLA]['by_Teacher_fitting_exposure']['exact_fit_peptide']['status'],'missing_class')
        self.assertEqual(r['comparison'][HLA]['original_EL_label_association']['status'],'descriptive_training_association')

    def test_replication_remains_unknown_even_when_keys_repeat(self):
        r=audit.replicate_evidence({'duplicate_pair_groups':3},[],[])
        self.assertIsNone(r['repeat_detection_probability']);self.assertEqual(r['statement'],audit.UNIDENTIFIABLE)
        self.assertIn('replicate',r['missing'][2].lower())
        self.assertEqual(r['status'],'unidentifiable_from_available_release')

    def test_native_sampler_exposure_and_nonmatched_intervention(self):
        original=audit.native_exposure(70069,1383509)
        self.assertEqual(original['EL_optimizer_steps_if_all_native_batches_processed'],70069)
        self.assertEqual(original['nominal_negatives_per_batch'],16)
        self.assertEqual(original['negative_rows_consumed'],1121104)
        removed=audit.native_exposure(70069-6937,1383509)
        self.assertEqual(removed['EL_optimizer_steps_if_all_native_batches_processed'],63132)
        self.assertNotEqual(original['negative_rows_consumed'],removed['negative_rows_consumed'])
        self.assertTrue(removed['not_a_matched_counterfactual'])

    def test_no_intervention_or_cutoff_selected(self):
        d=audit.summarize([self.score()],[HLA]);r=audit.intervention_context(d)
        self.assertIsNone(r['selected_intervention']);self.assertIsNone(r['selected_cutoff'])
        self.assertEqual(r['next_experiment']['type'],'blinded_repeat_detection_validation_before_curation')
        self.assertNotIn('overrides',r)

    def test_input_hash_gate_and_read_only_sources(self):
        p=self.root/'original.csv';p.write_text('mhc,pep,tgt\n'+HLA+',AAAAAAAAA,1\n')
        before=raw.sha256_file(p);self.assertEqual(list(audit.original_rows(p)),[[HLA,'AAAAAAAAA','1']])
        self.assertEqual(raw.sha256_file(p),before)
        config={'inputs':{'el_original':{'area':'runs','relative_path':'original.csv','sha256':'0'*64}}}
        with self.assertRaises(ValueError):audit.resolve_inputs(config,self.paths,{'el_original':p})

    def test_reject_corrected_and_sealed_overrides(self):
        for name in ('el_train_low_only.csv','im_test.csv','pseudolabel_overrides.csv.gz'):
            config={'inputs':{'el_original':{'area':'runs','relative_path':'original.csv','sha256':'0'*64}}}
            with self.assertRaises(ValueError):audit.resolve_inputs(config,self.paths,{'el_original':self.root/name})

    def test_reject_changed_reference_threshold_or_schema(self):
        c=audit.load_config(self.paths.repository_root/audit.CONFIG)
        c['descriptive_reference_only']['historical_low_lt_hours']=2
        p=self.root/'config.json';p.write_text(raw.json_report(c))
        with self.assertRaises(ValueError):audit.load_config(p)

    def test_read_only_default_and_deterministic_json(self):
        sample={'el_positive_stability.json':{'n':3,'interpretation':'predictions_only'}}
        with patch.object(audit,'inspect',return_value=(sample,[])),patch.object(audit.raw,'write_report') as write:
            a=audit.execute(config_path='fixture',paths=self.paths)
            b=audit.execute(config_path='fixture',paths=self.paths)
        self.assertEqual(raw.json_report(a),raw.json_report(b));write.assert_not_called()
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_sparse_undefined_auc(self):
        r=audit.summarize([self.score()],[HLA])
        self.assertIsNone(r['comparison'][HLA]['original_EL_label_association']['ROC_AUC'])

    def test_heldout_low_range_errors_from_frozen_model_not_el_relabeling(self):
        rows=[SimpleNamespace(observation_id=str(i),original_allele=HLA,original_peptide=str(i),original_measurement_text=v)
              for i,v in enumerate(('0.4','0','1'))]
        partition={'assignments':[{'observation_id':str(i),'partition':'train' if i==0 else 'validation'} for i in range(3)]}
        self.context.model.predict_stability=lambda peptide,hla:{'predicted_half_life_hours':{'1':.25,'2':.75}[peptide]}
        metrics=audit.teacher.metrics([0,1],[.25,.75])
        saved={'results':{'overall':{'teacher':metrics},HLA:{'teacher':metrics}}}
        with patch.object(audit.teacher,'load_population',return_value=(rows,{})),patch.object(audit.teacher,'verify_partition'):
            r=audit.teacher_context(self.context,self.root/'registry',partition,saved)
        self.assertTrue(r['saved_metrics_reproduced']);self.assertFalse(r['new_fitting_performed'])
        self.assertEqual(r['heldout_regions']['source_reported_zero']['n'],1)
        self.assertEqual(r['heldout_regions']['prediction_lt_historical_1h']['n'],2)
        self.assertTrue(r['by_HLA'][HLA]['validation_sparse_below10'])
        self.assertEqual(r['by_HLA'][HLA]['absolute_calibration_for_EL'],'not_established')

    def test_cli_preserves_old_commands_and_read_only_default(self):
        from stability_label_curation.__main__ import main
        for name in ('el-positive-analysis','bigmhc-worker','teacher','allele-diagnostics'):
            with redirect_stdout(io.StringIO()),self.assertRaises(SystemExit) as error:main([name,'--help'])
            self.assertEqual(error.exception.code,0)
        with patch.object(audit,'execute',return_value={'status':'analysis_only'}) as call,redirect_stdout(io.StringIO()):
            self.assertEqual(main(['el-positive-analysis','--json']),0)
        self.assertIsNone(call.call_args.kwargs['out'])

    def test_safe_json_csv_png_publication_and_offline_replay(self):
        run=self.paths.project_runs_dir/'analysis-test';(run/'reports').mkdir(parents=True)
        config=self.root/'config.json';config.write_text('{}')
        group=audit.describe([.5])
        reports={'teacher_coverage_alignment.json':{},'el_positive_stability.json':{'by_HLA':{HLA:group}},
                 'el_negative_context.json':{'by_HLA':{HLA:group}},
                 'teacher_reliability.json':{'by_HLA':{HLA:{'saved_validation_metrics':{'n':20,'spearman_hours':.5},'validation_sparse_below10':False}}}}
        manifest={'configuration':{'file':{'path':str(config),'sha256':raw.sha256_file(config)}},
                  'data_provenance':{'input_artifacts':[]},'git':{'commit_sha':'c'*40}}
        png=b'\x89PNG\r\n\x1a\nfixture'
        with patch.object(audit,'inspect',return_value=(reports,[])),patch.object(audit.teacher,'_run',return_value=(run,manifest)),\
             patch.object(audit,'render_figures',return_value={'figure.png':png}),patch('importlib.metadata.version',return_value='fixture'):
            audit.execute(config_path=config,out=run,paths=self.paths)
            result=audit.execute(config_path=config,out=run,paths=self.paths,verify_existing=True)
            self.assertTrue(result['offline_deterministic_reproduction'])
            self.assertEqual((run/'reports/figure.png').read_bytes(),png)
            with self.assertRaises(FileExistsError):audit.execute(config_path=config,out=run,paths=self.paths)
            (run/'reports/figure.png').write_bytes(b'changed')
            with self.assertRaises(ValueError):audit.execute(config_path=config,out=run,paths=self.paths,verify_existing=True)

    def test_actual_DTU_key_values_remain_separate_from_EL_predictions(self):
        score=self.score(value='0.25');score['DTU_source_exact_pair']='1'
        result=audit.summarize([score],[HLA],{(HLA,'AAAAAAAAA'):0.0})
        matched=result['positive']['matched_DTU_key_measurements']['by_source_partition']
        self.assertEqual(matched['all']['reported_hours']['source_reported_zero_count'],1)
        self.assertEqual(matched['all']['predicted_hours']['quantiles_hours']['p50'],.25)
        self.assertEqual(matched['heldout_pair']['reported_hours']['n'],1)
        self.assertNotIn('repeat_detection_probability',matched)
        with self.assertRaises(ValueError):audit.summarize([self.score()],[HLA],{(HLA,'AAAAAAAAA'):0.0})
