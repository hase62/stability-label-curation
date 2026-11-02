# HLA epoch監査・拡張学習報告

状態: **IN_PROGRESS**。取得時刻: 2026-11-02T05:58:34.449766+00:00。

既存の1 epoch結果・コード・checkpointを変更せず、新しいworktree/runだけを使用。新しい外部IM AP/AUROC/CI、bootstrapは計算していない。

## Phase A：認証済みの履歴

Task2.17 A/B/P、Task2.19 L/P、Task2.21 S/Pは、設定・stage完了receipt・全step数・checkpoint実ファイルを照合し、いずれもEL1→IM1、seed42を確認。Bが本拡張のWに対応する。
pilotのEL全適格集団は1,453,578行（70,069陽性・1,383,509陰性）。各EL1 epochは70,069更新、1,191,173 sampled exposures。IMは3,428行（955陽性・2,473陰性）を入力し、all-negative batch1個をskipして214更新・3,412実最適化exposures。行数と反復使用したexposure数を区別する。
pilotには独立EL validationがない。保存されたEL_proxyはIM dev383（120陽性・263陰性）上の指標であり、EL検証lossとは呼べない。1回のstageとbatch loss traceから収束や最適epochを証明できない。

| pilot arm | EL更新BCE | IM更新BCE | 完了epoch |
|---|---:|---:|---|
| 2_17 A | 0.07459771823145628 | 0.656963800769059 | EL1 / IM1 |
| 2_17 B | 0.07152760372664593 | 0.6639554028214771 | EL1 / IM1 |
| 2_17 P | 0.07466683711614468 | 0.6521112888108105 | EL1 / IM1 |
| 2_19 L | 0.06991785775758853 | 0.6606276532829437 | EL1 / IM1 |
| 2_19 P | 0.07187570625464959 | 0.6615188367760895 | EL1 / IM1 |
| 2_21 S | 0.07554319403488106 | 0.6339946823131297 | EL1 / IM1 |
| 2_21 P | 0.07593205745331155 | 0.6462374263883056 | EL1 / IM1 |

### データ数が変わる理由と補助学習の比較

Task2.23は、既に固定されたIM validation 665配列とexact一致するEL11行（陽性10・陰性1）を除外後、残りを配列group単位でEL学習/検証に分割。学習1,308,196行（陽性63,053・陰性1,245,143）、検証145,371行（陽性7,006・陰性138,365）。train/validationの配列・peptide–HLA overlapは0。今回も同じmanifestを再利用し、分割を作り直していない。
Task2.21/2.24は同じ原Teacher、414→1 linear補助head（415 scalar、head seed22042）、positive anchorのwithin-HLA rank target、batch平均BCE + 0.1×anchor MSE、IMではheadを外す設計。`audit/auxiliary_original_code_comparison.json`に元commitのクラス・関数AST fingerprintを記録。原headとlossの一致を確認し、epoch持続optimizer対応等の差は別扱い。Task2.21のrank参照は70,069陽性全体、2.24は学習陽性63,053のみ。学習予算はEL1/IM1対EL10/IM20であり、同一人口・予算の再現ではない。

### 長時間学習と収束の限界

A(Task2.23)はEL候補epoch1,2,4,6,8,10のうち検証AP最大で10を選択、10で予算終了。非候補epoch9のAPは10より高い。IM20は過去Task2.22の同一内部検証集団で選んだ固定期間であり、外部IM評価で選択していない。Early stoppingによる停止ではない。
A EL1→10: train update BCE 0.07676806662802817 → 0.048550949674902616; validation BCE 0.05444368720646589 → 0.04589545446132882; AP 0.8439537356930504 → 0.8800377430103999. 後半もAPは変動し、完全収束は未証明。
A EL10からの内部IM開発fit: epoch1→20のtrain eval BCE 0.6602947230890317 → 0.38672249137616177; validation BCE 0.6787353846144051 → 0.5377242659862118. 最小validation BCEはepoch15で0.5301019749210458、epoch20では悪化。validation APは0.42156030932768435 → 0.48932786204500645。損失の最適化とランキング改善は同一ではなく、20 epochを一意に収束済みとは呼べない。
Aのfinal full-IM20は全3,428行で再fitし、held-out IM validation lossは存在しない。学習eval BCEだけを収束の独立証拠にはしない。
Task2.24 S/P: fixed EL10/IM20、早期停止・外部IMによる選択なし。EL training BCEはS 0.0772223830925593→0.04799678922560008、P 0.07767441991162882→0.04892452827373744。SのMSEは0.0766449973715527→0.04714387580562254、Pは0.09782460800490728→0.09297911447232078。独立EL検証AP/AUROC/BCEはこの実行経路に保存されていない。改善するtrain lossだけでgeneralizationの収束を主張しない。
Task2.31 W/P: fixed EL10、IMなし。これは上位陽性upweightで、本実験の両方向Wとは違う。検証BCEはW 0.05467126038425421→0.04612716631058239、P 0.05418433348925672→0.045394203876895634。全epochとAP/AUROCは保存済みcurveを同梱。AはTask2.23を再利用。
Task2.37: Jappe実測Tm（kinetic half-lifeではない）710 ligand＋11,360 decoy、A EL10から最終出力415 scalarのみ更新、20 passes、seeds123/456/789、D/P/T。dropout/BNをeval固定し、class-balanced BCEをsample-weight sumで割る。checkpointは最終20 pass、IM fitなし。新しいW/Lのnative BCE分母とは異なる別目的の転移実験。held-out adaptation-validation curveがなく、soft-target Tとbinary Dのloss値は直接比較しない。旧技術reload修復とD123の正確elapsed不明も原記録どおり保持。
Task2.41b H/R1–R5: fixed EL10、seed42、IMなし。各群の陽性6,279を物理削除し、EL学習1,301,917行（56,774陽性・1,245,143陰性）。Aは元1,308,196行のEL10。最終epoch固定、early stoppingなし。全6群の保存検証curveを同梱し、削除後集団を今回のA/W/Lに流用しない。

## Phase B：固定条件と実施状況

preflight PASS、56 scientific focused tests PASS（失敗0・skip0、CUDA loss/gradient checksを含む）＋process分離2 tests PASS。事前固定commit: `72eb757df7836450956c37adbf0f0a256b500cc5`。
追加点検で、同一Python内の学習後推論でinterop thread設定を二度呼ぶと失敗することを確認。科学実装・設定を一切変えず、実行管理のみcommit `a8ec298`で別プロセス推論へ分離した。元supervisorだけを置換し、4つの稼働中fitは停止・再学習せず維持。元workerの予測前setup失敗receiptも残し、完成checkpointから初回の実モデル推論を新プロセスで行う。その他の失敗を自動retryしない。
paired seeds42/123/456。A42は元EL10とfinal full-IM20をSHA256・runtime・source・初期値で確認して再利用。A123/A456とW/L全6 fitは同じseedごとに新規初期化。全群固定EL10→IM20、lr5e-5、native AdamW、1陽性+16陰性、persistent optimizer、native batch-row BCE分母、元ラベル、同一HLA encoding。評価値で期間・checkpoint・seedを選ばない。
学習陽性のみで事前計算したrankに基づき、W=1+0.5(r−0.5)、L=min(1,W)。このrank参照範囲は後期protocolと一致するがpilot全陽性rankと異なるため明記する。Wの平均重み1、Lの平均重み0.9375002668439971、31,512陽性downweight、Wでは31,512陽性upweight、陰性weight1。元Teacher全63,053陽性binding PASS、除外0、ラベル変更0。
各seedのW/Lは、同seed Aの実際の全ordered batch hash・skip mask・optimizer設定・RNG境界に一致することを学習中に検証。IMでは重み付けせずnative4パラメータのみ更新。

| arm | seed | 状態 | 実完了EL epoch | 実完了IM epoch | predictionファイル数 |
|---|---:|---|---:|---:|---:|
| A | 42 | REUSED_AUTHENTICATED | 10 | 20 | 0 |
| W | 42 | RUNNING | 0 | 0 | 0 |
| L | 42 | RUNNING | 0 | 0 | 0 |
| A | 123 | RUNNING | 0 | 0 | 0 |
| W | 123 | NOT_STARTED | 0 | 0 | 0 |
| L | 123 | NOT_STARTED | 0 | 0 | 0 |
| A | 456 | RUNNING | 0 | 0 | 0 |
| W | 456 | NOT_STARTED | 0 | 0 | 0 |
| L | 456 | NOT_STARTED | 0 | 0 | 0 |

予測はEL-onlyとIM-adaptedを別ファイルにし、各stageでIMPROVE7,788行・Neo267行。実際に保存済みの行数/SHA256は`prediction_files.csv`とcheckpoint manifestを参照。未生成の予測や未完了epochを完了と数えていない。
新規IM AP/AUROC・paired差・CIはMac L2へ引き継ぐ。IMPROVEは既に繰り返し参照した探索的集団であり、独立確認ではない。Neoの患者/assay crosswalk不完全という既存制約も維持する。

## Figure2aへの提案

現時点では1 epoch結果をpilotとして補足資料へ移すのが妥当。1 epoch lossだけで十分な学習を確認できず、Aの長時間曲線には追加学習による変化がある。一方、長時間版はsplit/rank参照集団が異なるため、旧pilotの数値を上書き・同一実験として置換してはならない。
新しいA/W/Lの全paired-seed fit、checkpoint reload、予測整合性とMac L2の固定評価が完了した後に、Figure2aを「共通長時間protocolの新しい探索的比較」として再構成することは可能。学習未完了またはIM評価未実施の段階で改善/悪化や置換完了とは結論しない。

## 原本と再現性

実パス・SHA256・JSON source記録はaudit/source_inventory.json、extended_source_inventory.json、pilot_checkpoint_file_verification.json。新規入力の指紋はreports/preflight.json、重みはreports/weights.json、各fitの実行commit・epoch・loss・checkpointとhashはreports/に保存。完全なstep logと大容量checkpointはWSL runに保持し、配布ZIPには含めない。
Windows known folderはPowerShellのShell:Downloadsから取得し、利用不能時だけ標準Desktopを使用。既存run、checkpoint、Git branchの書換え、merge/push、外部送信は実施していない。
