"""Exercise the published jq report with synthetic Kubernetes exports."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPORT = (Path(__file__).resolve().parents[1] / 'content/field-notes'
          / 'rancher-retirement-investigation-command-index/storage-map.jq')


def item(name, namespace=None, spec=None, status=None, **metadata):
    meta = dict(name=name, uid=name + '-uid', **metadata)
    if namespace is not None:
        meta['namespace'] = namespace
    return dict(metadata=meta, spec=spec or {}, status=status or {})


@unittest.skipUnless(shutil.which('jq'), 'jq is required for the published report')
class StorageMapTests(unittest.TestCase):
    def run_report(self, **inputs):
        with tempfile.TemporaryDirectory() as directory:
            command = ['jq', '-n']
            for name in ('pods', 'pvcs', 'pvs', 'attachments'):
                path = Path(directory) / (name + '.json')
                value = inputs.get(name, [])
                path.write_text(json.dumps({'items': value}))
                command.extend(['--slurpfile', name, str(path)])
            command.extend(['-f', str(REPORT)])
            return subprocess.run(command, capture_output=True, text=True)

    def report(self, **inputs):
        result = self.run_report(**inputs)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_failed_deleting_pod_is_preserved_and_namespace_join_is_exact(self):
        def pod(name, namespace):
            return item(name, namespace,
                        spec={'nodeName': 'monitor-a', 'volumes': [
                            {'persistentVolumeClaim': {'claimName': 'data'}}]},
                        status={'phase': 'Failed'}, deletionTimestamp='2026-08-21T18:28:32Z')
        result = self.report(
            pods=[pod('test-a', 'default'), pod('other', 'other-namespace')],
            pvcs=[item('data', 'default', {'volumeName': 'pv-a'}, {'phase': 'Bound'})],
            pvs=[item('pv-a', spec={'csi': {'driver': 'example.csi', 'volumeHandle': 'backend-a'},
                                  'persistentVolumeReclaimPolicy': 'Delete'})],
            attachments=[item('attach-a', spec={'source': {'persistentVolumeName': 'pv-a'},
                                               'nodeName': 'monitor-a'}, status={'attached': True})])
        consumers = result['volumes'][0]['claims'][0]['consumers']
        self.assertEqual([c['pod'] for c in consumers], ['test-a'])
        self.assertEqual(consumers[0]['phase'], 'Failed')
        self.assertEqual(consumers[0]['deleting'], '2026-08-21T18:28:32Z')
        self.assertEqual(result['pod_claims_without_listed_pvc'][0]['pod'], 'other')

    def test_false_and_unknown_attachment_states_are_distinct(self):
        spec = {'source': {'persistentVolumeName': 'pv-a'}}
        result = self.report(pvs=[item('pv-a')], attachments=[
            item('detached', spec=spec, status={'attached': False}),
            item('unknown', spec=spec)])
        self.assertEqual([a['attached'] for a in result['volumes'][0]['attachments']], [False, None])

    def test_unresolved_references_and_unattached_volumes_are_not_dropped(self):
        result = self.report(
            pvcs=[item('unbound', 'default'), item('missing', 'default', {'volumeName': 'gone'})],
            pvs=[item('retained', spec={'persistentVolumeReclaimPolicy': 'Retain'})],
            attachments=[item('orphan', spec={'source': {'persistentVolumeName': 'gone'}})])
        self.assertEqual(len(result['claims_without_listed_pv']), 2)
        self.assertEqual(result['attachments_without_listed_pv'][0]['pv'], 'gone')
        self.assertEqual(result['volumes'][0]['attachments'], [])
        self.assertEqual(result['volumes'][0]['pv'], 'retained')

    def test_bad_list_shape_or_missing_identity_fails(self):
        for value in (None, {}, [dict(spec={})], [item('pod-without-namespace')]):
            with self.subTest(value=value):
                result = self.run_report(pods=value)
                self.assertNotEqual(result.returncode, 0)

    def test_empty_successful_lists_produce_empty_report(self):
        result = self.report()
        self.assertEqual(result['counts']['attachments'], 0)
        self.assertEqual(result['volumes'], [])


if __name__ == '__main__':
    unittest.main()
