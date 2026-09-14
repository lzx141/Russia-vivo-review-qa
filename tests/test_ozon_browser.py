import unittest
from unittest.mock import patch

from src.crawler import ozon_crawler


class TestOzonBrowser(unittest.TestCase):
    def test_creates_chrome_even_when_edge_is_installed(self):
        with patch.object(ozon_crawler.os.path, 'exists', return_value=True), \
                patch.object(ozon_crawler.webdriver, 'Edge') as edge, \
                patch.object(ozon_crawler.webdriver, 'Chrome') as chrome, \
                patch.object(ozon_crawler, '_inject_anti_detect') as inject:
            driver = ozon_crawler._create_driver(headless=False)
        chrome.assert_called_once()
        edge.assert_not_called()
        self.assertIs(driver, chrome.return_value)
        inject.assert_called_once_with(driver)
        self.assertNotIn('--headless=new', chrome.call_args.kwargs['options'].arguments)

    def test_chrome_failure_is_reported_without_edge_fallback(self):
        with patch.object(ozon_crawler.webdriver, 'Edge') as edge, \
                patch.object(ozon_crawler.webdriver, 'Chrome',
                             side_effect=RuntimeError('Chrome driver unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'Chrome driver unavailable'):
                ozon_crawler._create_driver()
        edge.assert_not_called()


if __name__ == '__main__':
    unittest.main()
