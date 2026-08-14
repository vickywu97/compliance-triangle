"""Unit tests for citation_parser — the parser must survive messy real-world
LLM outputs, not just the canonical 《法律》第X条 shape."""
import unittest

from compliance_triangle.citation_parser import (
    extract_citations, cn2int, _article_key,
)


class TestCn2Int(unittest.TestCase):
    def test_digits_pass_through(self):
        self.assertEqual(cn2int("142"), 142)

    def test_basic(self):
        self.assertEqual(cn2int("十二"), 12)
        self.assertEqual(cn2int("一百零五"), 105)
        self.assertEqual(cn2int("五百八十四"), 584)
        self.assertEqual(cn2int("二千三百"), 2300)

    def test_article_key_zhi(self):
        self.assertEqual(_article_key(234, "之一"), "234.001")
        self.assertEqual(_article_key(142, ""), "142")


class TestExtractCitations(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(extract_citations(""), [])
        self.assertEqual(extract_citations("这是一段没有引注的泛泛而谈。"), [])

    def test_standard(self):
        out = extract_citations("依据《公司法》第142条进行回购。")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["law_name"], "公司法")
        self.assertEqual(out[0]["article_no"], "142")

    def test_no_tiao_marker(self):
        # some models omit 条: 《公司法》第一百四十二条
        out = extract_citations("《公司法》第一百四十二条规定了股份回购。")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["law_name"], "公司法")
        self.assertEqual(out[0]["article_no"], "142")

    def test_zhi_variant(self):
        out = extract_citations("《刑法》第234条之一规定了故意伤害。")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["article_no"], "234.001")

    def test_continuation_same_law(self):
        # 、第X条 continues the preceding law name
        out = extract_citations("《公司法》第15条、第142条规定了担保与回购。")
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["law_name"], "公司法")
        self.assertEqual(out[0]["article_no"], "15")
        self.assertEqual(out[1]["law_name"], "公司法")
        self.assertEqual(out[1]["article_no"], "142")

    def test_english_law_name(self):
        out = extract_citations("Under 《Company Law》Article 142 the company may repurchase.")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["law_name"], "公司法")  # mapped via EN_LAW_ALIASES
        self.assertEqual(out[0]["article_no"], "142")

    def test_english_lowercase_article(self):
        out = extract_citations("《Patent Law》article 6 applies.")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["law_name"], "专利法")
        self.assertEqual(out[0]["article_no"], "6")

    def test_nested_parenthetical(self):
        # citation inside （…） plus a second citation after a comma
        out = extract_citations(
            "（依据《公司法》第142条）并参照《证券法》第40条执行。")
        laws = [c["law_name"] for c in out]
        self.assertIn("公司法", laws)
        self.assertIn("证券法", laws)

    def test_mixed_laws(self):
        out = extract_citations(
            "《公司法》第142条、《个人所得税法》第2条及《民法典》第584条。")
        self.assertEqual(len(out), 3)
        self.assertEqual([c["law_name"] for c in out],
                         ["公司法", "个人所得税法", "民法典"])

    def test_quoted_text_after_colon(self):
        out = extract_citations(
            "《公司法》第142条：公司不得收购本公司股份。但是，有下列情形之一的除外。")
        self.assertEqual(len(out), 1)
        self.assertIn("公司不得收购本公司股份", out[0]["quoted"])

    def test_bare_citation_no_quote(self):
        out = extract_citations("参见《公司法》第142条。")
        self.assertEqual(out[0]["quoted"], "")

    def test_repealed_law_name_citation(self):
        # deprecated law name must still be extracted so verify can flag it
        out = extract_citations("旧法见《旧公司法》第16条。")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["law_name"], "旧公司法")
        self.assertEqual(out[0]["article_no"], "16")


if __name__ == "__main__":
    unittest.main()
