"""Enable V2 only for the exact inputs/code that passed the full Python suite."""
from pathlib import Path
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.deps'),str(ROOT)]
from hoklab.strength_v2 import fingerprint
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'));result=unittest.TextTestRunner(verbosity=2).run(suite)
gate={'passed':result.wasSuccessful(),'input_fingerprint':fingerprint(),'python_tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'validation_scope':'source contracts, numerical invariants, V1 regression, independent lane pools, 30/70 composite and labeled daily fallback, temporal isolation',
      'predictive_superiority':'unproven; descriptive temporal associations do not establish optimal weights'}
(ROOT/'output/qa').mkdir(parents=True,exist_ok=True)
(ROOT/'output/qa/v2-validation-gate.json').write_text(json.dumps(gate,indent=2),encoding='utf-8')
print(json.dumps(gate));raise SystemExit(0 if gate['passed'] else 1)
