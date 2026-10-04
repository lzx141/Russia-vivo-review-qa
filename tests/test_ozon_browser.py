import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

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

    def test_uses_configured_profile_to_preserve_antibot_cookie(self):
        with TemporaryDirectory() as temp_dir, \
                patch.dict(ozon_crawler.os.environ, {
                    'OZON_CHROME_USER_DATA_DIR': temp_dir,
                }), \
                patch.object(ozon_crawler.webdriver, 'Chrome') as chrome, \
                patch.object(ozon_crawler, '_inject_anti_detect'):
            ozon_crawler._create_driver(headless=False)

        arguments = chrome.call_args.kwargs['options'].arguments
        self.assertIn(
            f'--user-data-dir={Path(temp_dir).resolve()}',
            arguments,
        )

    def test_search_redirect_does_not_open_unrelated_product(self):
        unrelated = MagicMock()
        unrelated.get_attribute.return_value = (
            'https://www.ozon.ru/product/xiaomi-note-15-123/'
        )
        unrelated.text = 'Xiaomi Note 15'
        driver = MagicMock()
        driver.find_elements.return_value = [unrelated]

        with patch('builtins.print'), \
                patch.object(ozon_crawler.time, 'sleep'), \
                patch.object(ozon_crawler, '_is_search_redirect_page',
                             return_value=False):
            opened = ozon_crawler._click_product_card_to_detail(
                driver,
                'iQOO Z10',
                MagicMock(),
            )

        self.assertFalse(opened)
        driver.execute_script.assert_not_called()

    def test_review_crawl_stops_when_redirect_has_no_matching_product(self):
        driver = MagicMock()
        wait = MagicMock()
        wait.until.side_effect = AssertionError(
            'review selectors must not run on a recommendation page'
        )

        with patch('builtins.print'), \
                patch.object(ozon_crawler.time, 'sleep'), \
                patch.object(ozon_crawler, '_create_driver',
                             return_value=driver), \
                patch.object(ozon_crawler, 'WebDriverWait',
                             return_value=wait), \
                patch.object(ozon_crawler, '_ensure_detail_page',
                             return_value=False):
            reviews = ozon_crawler.crawl_ozon_reviews_by_url(
                'https://www.ozon.ru/product/sold-out/',
                'iQOO Z10',
                '2026-09-01',
                '2026-09-30',
            )

        self.assertEqual([], reviews)
        driver.quit.assert_called_once_with()

    def test_qa_crawl_stops_when_redirect_has_no_matching_product(self):
        driver = MagicMock()
        wait = MagicMock()
        wait.until.side_effect = AssertionError(
            'question selectors must not run on a recommendation page'
        )

        with patch('builtins.print'), \
                patch.object(ozon_crawler.time, 'sleep'), \
                patch.object(ozon_crawler, '_create_driver',
                             return_value=driver), \
                patch.object(ozon_crawler, 'WebDriverWait',
                             return_value=wait), \
                patch.object(ozon_crawler, '_ensure_detail_page',
                             return_value=False):
            questions = ozon_crawler.crawl_ozon_qa_by_url(
                'https://www.ozon.ru/product/sold-out/',
                'iQOO Z10',
                '2026-09-01',
                '2026-09-30',
            )

        self.assertEqual([], questions)
        driver.quit.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
