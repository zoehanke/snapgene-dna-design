"""External-converter ownership, with literal I/O controls and real child processes."""
from repository_paths import RUNTIME_SCRIPTS
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import validate_roundtrip


HELPER = '''
import os,pathlib,subprocess,sys,time
sys.path.insert(0,sys.argv[1])
import validate_roundtrip as validation
root=pathlib.Path(sys.argv[2]);label=sys.argv[3]
(root/('ready-'+label)).write_text('ready',encoding='utf-8')
while not (root/'start').exists():time.sleep(0.01)
def convert(args,**kwargs):
    marker=root/'exclusive-converter'
    try:descriptor=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:return subprocess.CompletedProcess(args,1,'','Concurrent converter use')
    try:
        time.sleep(0.3)
        pathlib.Path(args[args.index('--output')+1]).write_bytes(b'constructed I/O output')
    finally:os.close(descriptor);marker.unlink()
    return subprocess.CompletedProcess(args,0,'','')
validation.subprocess.run=convert
validation._official_convert(str(root/'shared-converter'),str(root/'input'),str(root/('output-'+label)),'test-format')
'''


class OfficialConversionConcurrencyTests(unittest.TestCase):
    def test_shared_converter_is_serialised_across_processes(self):
        with tempfile.TemporaryDirectory(prefix='converter-ownership-') as temporary:
            root=Path(temporary)
            processes=[subprocess.Popen([sys.executable,'-X','utf8','-B','-c',HELPER,str(RUNTIME_SCRIPTS),str(root),str(i)],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8') for i in range(2)]
            try:
                deadline=time.monotonic()+15
                while not all((root/('ready-'+str(i))).exists() for i in range(2)):
                    self.assertLess(time.monotonic(),deadline)
                    time.sleep(0.02)
                (root/'start').write_text('start',encoding='utf-8')
                for process in processes:
                    stdout,stderr=process.communicate(timeout=15)
                    self.assertEqual(process.returncode,0,stdout+stderr)
                for i in range(2):self.assertEqual((root/('output-'+str(i))).read_bytes(),b'constructed I/O output')
            finally:
                for process in processes:
                    if process.poll() is None:process.kill();process.communicate()

    def test_success_exit_without_output_stays_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            completed=subprocess.CompletedProcess([],0,'','')
            with mock.patch.object(validate_roundtrip.subprocess,'run',return_value=completed):
                with self.assertRaisesRegex(RuntimeError,'did not create expected output'):
                    validate_roundtrip._official_convert(str(root/'converter'),str(root/'input'),str(root/'absent'),'test-format')

    def test_nonzero_converter_exit_stays_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            completed=subprocess.CompletedProcess([],4,'','constructed converter refusal')
            with mock.patch.object(validate_roundtrip.subprocess,'run',return_value=completed):
                with self.assertRaisesRegex(RuntimeError,'conversion failed'):
                    validate_roundtrip._official_convert(str(root/'converter'),str(root/'input'),str(root/'output'),'test-format')


if __name__=='__main__':
    unittest.main()
