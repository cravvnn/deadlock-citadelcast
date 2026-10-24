"""Owning offline tests and a discriminating in-memory regression mutation."""
from pathlib import Path
import contextlib
import hashlib
import inspect
import io
import json
import time
import unittest
import obstruction
import test_obstruction
import test_dynamic_obstruction

HERE=Path(__file__).resolve().parent
start=time.perf_counter()
stream=io.StringIO()
suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(m) for m in
                        (test_obstruction,test_dynamic_obstruction)])
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(HERE/'tests.log').write_text(stream.getvalue())
# Defeating visibility validation must make the observable blocked-shot test fail.
namespace=dict(vars(obstruction))
source=inspect.getsource(obstruction.Resolver)
needle='if not clear(camera,point,0,"visibility"): raise Refused("hero sightline blocked")'
assert needle in source
exec(source.replace(needle,'if False: raise Refused("hero sightline blocked")'),namespace)
old=test_obstruction.Resolver
try:
    test_obstruction.Resolver=namespace['Resolver']
    mutation_stream=io.StringIO()
    mutation=unittest.TestSuite([test_obstruction.ResolverTests('test_non_solid_visual_obstruction_is_still_a_blocked_shot')])
    mutated=unittest.TextTestRunner(stream=mutation_stream).run(mutation)
finally: test_obstruction.Resolver=old
(HERE/'mutation-visibility.log').write_text(mutation_stream.getvalue())
record={'kind':'synthetic contract checks, no live compatibility claim',
        'tests_run':result.testsRun,'passed':result.wasSuccessful(),
        'visibility_removal_detected':len(mutated.failures)==1 and not mutated.errors,
        'elapsed_seconds':time.perf_counter()-start,
        'source_sha256':{p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in
                         ('obstruction.py','test_obstruction.py','test_dynamic_obstruction.py','run_checks.py')}}
(HERE/'test-review.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
if not result.wasSuccessful() or not record['visibility_removal_detected']: raise SystemExit(1)
