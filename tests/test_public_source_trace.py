"""Public database adapter controls use a real loopback server, never NCBI."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from repository_paths import SKILL_ROOT

sys.path.insert(0, str(SKILL_ROOT/'scripts'))
import online_sources
from evidence_trace.runtime import traced_run
from evidence_trace.recorder import load_events, project


@contextlib.contextmanager
def local_database(payload_override=None):
    record = SeqRecord(Seq('ACGT'*18), id='SYNTH01.3', name='SYNTH01',
                       annotations={'molecule_type':'DNA', 'date':'01-JAN-2000'})
    stream = io.StringIO(); SeqIO.write(record, stream, 'genbank')
    payload = stream.getvalue()
    if payload_override is not None:payload=payload_override
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            if '/efetch.fcgi' in self.path:
                text = payload
            elif '/esearch.fcgi' in self.path:
                text = json.dumps({'esearchresult':{'idlist':['77']}})
            else:
                text = json.dumps({'result':{'77':{'caption':'SYNTH01',
                    'accessionversion':'SYNTH01.3','title':'Synthetic software vector'}}})
            self.send_response(200); self.end_headers(); self.wfile.write(text.encode('utf-8'))
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    original = socket.socket.connect
    def loopback_only(sock, address):
        if address[0] not in ('127.0.0.1','::1'):
            raise AssertionError('Automated database test attempted an external connection')
        return original(sock,address)
    try:
        with patch.object(online_sources,'NCBI_EUTILS',f'http://127.0.0.1:{server.server_port}'), \
             patch.object(socket.socket,'connect',loopback_only):
            yield payload, requests
    finally:
        server.shutdown(); server.server_close(); worker.join()


class PublicSourceTraceTests(unittest.TestCase):
    def test_failed_fetch_preserves_existing_record_and_its_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)/'prior.gb'; receipt=out.with_suffix('.gb.source.json')
            out.write_bytes(b'previous bytes'); receipt.write_text('{"previous":true}',encoding='utf-8')
            with patch.object(online_sources,'_get',side_effect=OSError('offline')), contextlib.redirect_stdout(io.StringIO()):
                code=online_sources.main(['fetch','SYNTH01.3','--allow-network','--out',str(out)])
            self.assertEqual(code,2)
            self.assertEqual(out.read_bytes(),b'previous bytes')
            self.assertEqual(json.loads(receipt.read_text(encoding='utf-8')),{'previous':True})

    def test_actual_invalid_or_wrong_record_is_not_a_verified_sequence(self):
        for payload, requested in [('Not a GenBank record','SYNTH01.3'),(None,'OTHER01.1')]:
            with self.subTest(requested=requested), local_database(payload):
                result=online_sources.fetch_genbank(requested)
            self.assertEqual(result['status'],'offline-unverified')
            self.assertNotIn('text',result)
            self.assertNotIn('source_sha256',result['source'])

    def test_explicit_environment_probe_uses_only_the_local_server(self):
        import check_env
        with local_database() as (_, requests):
            result=check_env.probe_online()
        self.assertEqual(result['status'],'available')
        self.assertEqual(len(requests),1)

    def test_environment_check_is_offline_without_an_explicit_probe(self):
        from test_kit_network_defaults import LAUNCHER
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); launcher=root/'blocked.py'; counter=root/'counter.json'
            launcher.write_text(LAUNCHER,encoding='utf-8')
            process=subprocess.run([sys.executable,'-X','utf8','-B',str(launcher),str(counter),
                str(SKILL_ROOT/'scripts/check_env.py'),'--json'],capture_output=True,encoding='utf-8')
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(json.loads(counter.read_text(encoding='utf-8'))['connection_attempts'],0)
            self.assertEqual(json.loads(process.stdout)['online']['status'],'not-requested')

    def test_fetched_record_has_independent_content_hash_and_source_node(self):
        with tempfile.TemporaryDirectory(prefix='来源-') as temp, local_database() as (payload, requests):
            root=Path(temp); settings=root/'trace.json'
            settings.write_text('{"trace_level":"observed"}',encoding='utf-8')
            @traced_run('public-database-test')
            def flow(out_dir):
                return online_sources.fetch_genbank('SYNTH01.3')
            with patch.dict(os.environ,{'SNAPGENE_TRACE_CONFIG':str(settings)}):
                result=flow(root,trace_dir=root/'trace')
            source=result['source']
            self.assertEqual(source['database'],'NCBI nucleotide')
            self.assertEqual(source['accession_version'],'SYNTH01.3')
            self.assertEqual(source['source_sha256'],hashlib.sha256(payload.encode('utf-8')).hexdigest())
            self.assertTrue(source['retrieved_at'].endswith('Z'))
            self.assertEqual(source['retrieval_status'],'verified-online')
            nodes=[row for row in project(load_events(root/'trace')[0])['nodes'] if row['kind']=='source']
            self.assertEqual(len(nodes),1)
            self.assertEqual(nodes[0]['source_sha256'],source['source_sha256'])
            self.assertEqual(len(requests),1)

    def test_default_cli_makes_zero_connection_attempts(self):
        attempts=[]
        def blocked(*args,**kwargs):
            attempts.append(True); raise OSError('Network is blocked in test')
        with patch.object(socket,'create_connection',blocked), patch.object(socket.socket,'connect',blocked), \
             contextlib.redirect_stdout(io.StringIO()):
            code=online_sources.main([])
        self.assertEqual(code,0)
        self.assertEqual(attempts,[])

    def test_public_cli_explicit_fetch_writes_exact_bytes_and_source_receipt(self):
        with tempfile.TemporaryDirectory() as temp, local_database() as (payload, requests):
            out=Path(temp)/'record.gb'
            with contextlib.redirect_stdout(io.StringIO()):
                code=online_sources.main(['fetch','SYNTH01.3','--allow-network','--out',str(out)])
            self.assertEqual(code,0)
            self.assertEqual(out.read_bytes(),payload.encode('utf-8'))
            source=json.loads(out.with_suffix('.gb.source.json').read_text(encoding='utf-8'))
            self.assertEqual(source['source_sha256'],hashlib.sha256(out.read_bytes()).hexdigest())
            self.assertEqual(len(requests),1)

    def test_public_cli_denies_fetch_without_explicit_network_flag(self):
        with local_database() as (_, requests), contextlib.redirect_stdout(io.StringIO()):
            code=online_sources.main(['fetch','SYNTH01.3'])
        self.assertEqual(code,2)
        self.assertEqual(requests,[])

    def test_raw_sequence_cannot_be_sent_as_an_accession(self):
        with patch.object(online_sources,'_get') as get:
            result=online_sources.fetch_genbank('ACGT'*20)
        self.assertEqual(result['status'],'refused-consent-required')
        get.assert_not_called()

    def test_failed_fetch_keeps_offline_status_and_never_supplies_sequence(self):
        with patch.object(online_sources,'_get',side_effect=OSError('synthetic offline')):
            result=online_sources.fetch_genbank('SYNTH01.3')
        self.assertEqual(result['status'],'offline-unverified')
        self.assertNotIn('text',result)
        self.assertEqual(result['source']['verification_status'],'unverified')
        self.assertNotIn('source_sha256',result['source'])

    def test_search_records_keep_version_and_retrieval_metadata(self):
        with local_database():
            result=online_sources.ncbi_search('synthetic record')
        self.assertEqual(result['records'][0]['accession_version'],'SYNTH01.3')
        self.assertEqual(result['source']['source_type'],'public-database-search')
        self.assertTrue(result['source']['source_sha256'])


if __name__=='__main__':unittest.main()
