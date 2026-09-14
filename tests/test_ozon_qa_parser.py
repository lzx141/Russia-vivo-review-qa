"""Ozon 问答解析（新版 webPDPListQuestions 结构）回归测试。"""
import unittest

from src.crawler import ozon_crawler


class _TextNode:
    def __init__(self, text):
        self.text = text


class _FakeQuestionCard:
    """按 XPath 返回预设文本的最小 DOM 替身"""

    def __init__(self, mapping):
        self.mapping = mapping

    def find_elements(self, by, value):
        return [_TextNode(t) for t in self.mapping.get(value, [])]


def _full_card():
    return _FakeQuestionCard({
        "./div[1]/div[2]/div[2]/div[1]": ["  Поддерживает ли eSIM?  "],
        "./div[1]/div[2]/div[2]/div[1]/span[1]": ["Поддерживает ли eSIM?"],
        "./div[1]/div[2]/div[2]/div[2]": ["Александр Б."],
        "./div[1]/div[2]/div[1]/div[1]": ["18 августа 2026"],
        "./div[1]/div[2]/div[1]/a": ["iQOO Смартфон iQOO 15 12/256 ГБ"],
        ".//div[@data-answer-uuid]/div[1]/div[3]/div[1]": ["Да, поддерживает."],
        ".//div[@data-answer-uuid]/div[1]/div[2]/div[1]": ["OZON"],
        ".//div[@data-answer-uuid]/div[1]/div[2]/div[2]": ["19 августа 2026"],
    })


class TestOzonQaParser(unittest.TestCase):
    def test_parses_new_question_card(self):
        parsed = ozon_crawler._parse_qa_item(_full_card())
        self.assertEqual("Поддерживает ли eSIM?", parsed["question"])
        self.assertEqual("Александр Б.", parsed["author"])
        self.assertEqual("18 августа 2026", parsed["publishDate"])
        self.assertEqual("iQOO Смартфон iQOO 15 12/256 ГБ", parsed["SKU"])
        self.assertEqual("Да, поддерживает.", parsed["content"])

    def test_uses_span_fallback_when_wrapper_is_empty(self):
        card = _FakeQuestionCard({
            "./div[1]/div[2]/div[2]/div[1]/span[1]": ["Есть ли NFC?"],
            "./div[1]/div[2]/div[2]/div[2]": ["Мария"],
        })
        parsed = ozon_crawler._parse_qa_item(card)
        self.assertEqual("Есть ли NFC?", parsed["question"])
        self.assertEqual("Мария", parsed["author"])
        self.assertEqual("", parsed["content"])

    def test_missing_question_is_not_a_question(self):
        """列表头/占位卡片没有正文，必须丢弃而不是产出空记录"""
        card = _FakeQuestionCard({"./div[1]/div[2]/div[1]/div[1]": ["1 января 2026"]})
        self.assertIsNone(ozon_crawler._parse_qa_item(card))

    def test_anonymous_author_default(self):
        card = _FakeQuestionCard({
            "./div[1]/div[2]/div[2]/div[1]": ["Когда поступит?"],
        })
        parsed = ozon_crawler._parse_qa_item(card)
        self.assertEqual("Аноним", parsed["author"])

    def test_qa_text_tolerates_missing_xpaths(self):
        class _Broken:
            def find_elements(self, by, value):
                raise RuntimeError("stale element reference")

        self.assertEqual("", ozon_crawler._qa_text(_Broken(), ("//a",)))


class TestOzonRating(unittest.TestCase):
    """星级必须按「亮星数量」读取：旧实现的 hashed class 已失效，导致全量记为 1 星"""

    @staticmethod
    def _driver(script_result):
        import types
        return types.SimpleNamespace(execute_script=lambda *a, **k: script_result)

    def test_uses_filled_star_count(self):
        self.assertEqual(4, ozon_crawler._read_rating(self._driver([5, 4]), object()))

    def test_uses_star_total_when_none_reported_filled(self):
        self.assertEqual(3, ozon_crawler._read_rating(self._driver([3, 0]), object()))

    def test_clamps_to_one_to_five(self):
        self.assertEqual(5, ozon_crawler._read_rating(self._driver([9, 9]), object()))

    def test_defaults_to_one_star_without_svg_data(self):
        class _NoSvgs:
            def find_elements(self, by, value):
                return []

        self.assertEqual(1, ozon_crawler._read_rating(self._driver([0, 0]), _NoSvgs()))

    def test_survives_script_errors(self):
        import types

        class _NoSvgs:
            def find_elements(self, by, value):
                return []

        def boom(*args, **kwargs):
            raise RuntimeError("javascript error")

        driver = types.SimpleNamespace(execute_script=boom)
        self.assertEqual(1, ozon_crawler._read_rating(driver, _NoSvgs()))


class TestOzonUrlHelpers(unittest.TestCase):
    def test_url_without_sort_strips_only_sort_param(self):
        self.assertEqual(
            "https://www.ozon.ru/product/x/",
            ozon_crawler._url_without_sort(
                "https://www.ozon.ru/product/x/?sort=published_at_desc"),
        )
        self.assertEqual(
            "https://www.ozon.ru/product/x/?at=abc",
            ozon_crawler._url_without_sort(
                "https://www.ozon.ru/product/x/?at=abc&sort=published_at_desc"),
        )

    def test_url_without_sort_is_identity_without_param(self):
        url = "https://www.ozon.ru/product/x/"
        self.assertEqual(url, ozon_crawler._url_without_sort(url))


class TestOzonProxyHygiene(unittest.TestCase):
    def test_clear_proxy_environment_removes_all_casing(self):
        import os

        names = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                 "http_proxy", "https_proxy", "all_proxy")
        saved = {name: os.environ.get(name) for name in names}
        try:
            for name in names:
                os.environ[name] = "http://127.0.0.1:7897"
            ozon_crawler.clear_proxy_environment()
            for name in names:
                self.assertNotIn(name, os.environ)
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
