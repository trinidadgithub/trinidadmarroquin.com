"""Synthetic local fixtures; no production evidence or infrastructure access."""

import csv
import importlib.util
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / 'content/field-notes'
          / 'nimble-storage-investigation-command-index/storage_evidence.py')
SPEC = importlib.util.spec_from_file_location('storage_evidence', SOURCE)
helper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helper)
A = 'pvc-00000000-0000-0000-0000-000000000001'
B = 'pvc-00000000-0000-0000-0000-000000000002'
C = 'pvc-00000000-0000-0000-0000-000000000003'
HEADER = 'Name Size Online Offline Usage Reserve % Limit % Path\n(MiB) Reason (MiB)\n'


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def save(self, name, value):
        path = self.root / name
        path.write_text(value)
        return path

    def journal(self, name, events):
        path = self.root / name
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['timestamp_utc', 'action', 'volume', 'result', 'detail'])
            for action, volume, result, detail in events:
                writer.writerow(['2026-11-20T12:00:00+00:00', action, volume, result, detail])
        return path

    def test_inventory_capacity_and_zero_pvc_datastore_listing(self):
        path = self.save('before', HEADER + f'{A} 1048576 No User 1024 0 100 default:/\n'
                         + f'{B} 1024 Yes N/A 2 0 100 default:/\n')
        report = helper.inventory(path)
        self.assertEqual(report['summary']['offline']['size_tib'], 1)
        self.assertEqual(report['summary']['online']['usage_mib'], 2)
        empty = self.save('after', HEADER + 'datastore-a 1024 Yes N/A 100 0 100 default:/\n')
        self.assertEqual(helper.inventory(empty)['summary']['total']['count'], 0)

    def test_malformed_duplicate_empty_and_error_captures_are_rejected(self):
        valid = f'{A} 1024 No User 2 0 100 default:/\n'
        for raw in ('', 'Permission denied', 'ERROR: failed', valid,
                    HEADER + valid + valid, HEADER + f'{A} 1024 No User\n',
                    HEADER + f'{A} 1024 Maybe User 2 0 100 default:/\n'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    helper.inventory(self.save('bad', raw))

    def test_timestamp_sort_retains_year_month_and_reports_unknown_names(self):
        raw = 'Volume Snapshot Size Online Status Uncompressed (MiB)\n'
        for suffix in ('2026-01-01::00:00:00.100', '2025-12-31::23:59:58.500', 'manual'):
            raw += f'{A} NSs-{A}-{suffix} 19073 No Okay 0 default:/\n'
        report = helper.snapshots(self.save('snaps', raw), A)
        self.assertEqual(report['earliest_name_timestamp'], '2025-12-31T23:59:58.500000')
        self.assertEqual(report['adjacent_intervals_seconds'], [1.6])
        self.assertEqual(report['names_without_timestamp'], 1)
        self.assertEqual(report['online_states'], {'No': 3})

    def test_wrong_volume_and_duplicate_snapshot_rejected(self):
        header = 'Volume Snapshot Online (MiB)\n'
        row = f'{A} snap-one 1024 No Okay 0 default:/\n'
        with self.assertRaises(ValueError):
            helper.snapshots(self.save('wrong', header + row), B)
        with self.assertRaises(ValueError):
            helper.snapshots(self.save('duplicate', header + row + row), A)

    def test_journal_events_quoted_csv_and_overlap(self):
        earlier = self.journal('earlier.csv', [('delete', A, 'success', 'checked, absent')])
        later = self.journal('later.csv', [
            ('check', A, 'missing', ''), ('check', B, 'missing', ''),
            ('delete_intent', C, 'started', ''), ('delete', A, 'success', '')])
        report = helper.journals([earlier, later])
        self.assertEqual(report['events']['delete,success'], 2)
        self.assertEqual(report['unique_successes'], [A])
        self.assertEqual(report['missing_with_prior_or_other_success'], [A])
        self.assertEqual(report['missing_without_success'], [B])
        self.assertEqual(report['intents_without_any_success'], [C])
        self.assertEqual(list(report['success_overlap_between_files'].values()), [[A]])

    def test_truncated_journal_and_schema_mismatch_rejected(self):
        header = 'timestamp_utc,action,volume,result,detail\n'
        for raw in (header + f'2026-11-20T12:00:00,delete,{A},success\n',
                    'timestamp,action,volume,result,detail\n'):
            with self.assertRaises(ValueError):
                helper.journals([self.save('bad.csv', raw)])

    def test_reconcile_separates_manual_absence_remaining_and_new_names(self):
        row = lambda name: f'{name} 1024 No User 2 0 100 default:/\n'
        original = self.save('original', HEADER + row(A) + row(B))
        final = self.save('final', HEADER + row(B) + row(C))
        scope = self.save('scope', A + '\n' + B + '\n')
        journal = self.journal('audit.csv', [('dry_run', A, 'pass', '')])
        report = helper.reconcile(Namespace(original=original, final=final,
                                            approved=scope, journals=[journal]))
        self.assertEqual(report['approved_still_present'], [B])
        self.assertEqual(report['absent_original_without_success'], [A])
        self.assertEqual(report['new_names_in_final'], [C])
        self.assertEqual(report['journal_analysis']['unique_successes'], [])

    def test_approval_rejects_duplicate_and_invalid_names(self):
        for raw in (A + '\n' + A, 'not-a-volume', ''):
            with self.assertRaises(ValueError):
                helper.names(self.save('scope', raw))


if __name__ == '__main__':
    unittest.main()
