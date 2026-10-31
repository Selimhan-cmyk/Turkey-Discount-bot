import unittest
from bot import parse_listing_page, parse_price


class DealParserTests(unittest.TestCase):
    def test_turkish_price(self):
        self.assertEqual(parse_price("1.849,99 TL"), 1849.99)
        self.assertEqual(parse_price("12.666 TL"), 12666.0)
        self.assertEqual(parse_price("1234.56 TL"), 1234.56)

    def test_extracts_hepsiburada_product_card(self):
        html = '''<div><a href="/urun-test-p-HBCV000123"><span>Örnek ürün fırsatı</span><div>Eski fiyat 2.000 TL, şimdi 1.750 TL</div></a></div>'''
        source = {"key": "hepsiburada", "name": "Hepsiburada", "url": "https://www.hepsiburada.com/kampanyalar"}
        items = parse_listing_page(html, source)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["price"], 1750.0)
        self.assertIn("Örnek ürün", items[0]["title"])

    def test_ignores_external_links(self):
        html = '''<div><a href="https://example.org/product"><span>Başka site ürünü</span> 99 TL</a></div>'''
        source = {"key": "hepsiburada", "name": "Hepsiburada", "url": "https://www.hepsiburada.com/kampanyalar"}
        self.assertEqual(parse_listing_page(html, source), [])


if __name__ == "__main__":
    unittest.main()
