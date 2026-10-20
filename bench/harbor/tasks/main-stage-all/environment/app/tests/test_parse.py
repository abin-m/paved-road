import unittest

from parse import parse_pair


class ParsePair(unittest.TestCase):
    def test_strips_spaces(self):
        self.assertEqual(parse_pair("name: api"), ("name", "api"))


if __name__ == "__main__":
    unittest.main()
