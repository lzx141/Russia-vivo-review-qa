import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from config.config import PRODUCT_URLS_EXCEL, PROJECT_ROOT
from src.crawler import ozon_crawler


class TestOzonCLI(unittest.TestCase):
    def test_default_entry_uses_current_project_configuration(self):
        with patch.object(ozon_crawler, 'crawl_from_excel') as crawl:
            self.assertEqual(0, ozon_crawler.main([]))
        self.assertEqual(PRODUCT_URLS_EXCEL, crawl.call_args.args[0])

    def test_dry_run_checks_links_without_launching_browser(self):
        with patch.object(ozon_crawler, '_create_driver') as driver:
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result = ozon_crawler.main(['--dry-run', '--start-date', '2026-08-01',
                                            '--end-date', '2026-08-31'])
        self.assertEqual(0, result)
        self.assertIn('2026-08-01', output.getvalue())
        driver.assert_not_called()

    def test_missing_input_reports_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stdout(io.StringIO()):
                result = ozon_crawler.main(['--excel', os.path.join(directory, 'absent.xlsx'),
                                            '--dry-run'])
        self.assertEqual(1, result)

    def test_direct_entry_works_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-X', 'utf8', os.path.join(PROJECT_ROOT, 'src', 'crawler',
                  'ozon_crawler.py'), '--dry-run'], cwd=directory,
                capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(PRODUCT_URLS_EXCEL, result.stdout)


if __name__ == '__main__':
    unittest.main()
