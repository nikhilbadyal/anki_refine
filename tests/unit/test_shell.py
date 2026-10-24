import unittest

from src.refine import shell


class Sidebar(unittest.TestCase):
    def test_theme_toggle_above_sync(self):
        out = shell.sidebar_html("decks", "User 1", [])
        self.assertIn("refine:sidebar:go:theme", out)
        self.assertIn("Dark mode", out)
        self.assertIn("Light mode", out)
        self.assertLess(out.index("rf-theme-toggle"), out.index("rf-sync"))

    def test_active_item(self):
        out = shell.sidebar_html("stats", "", [])
        self.assertEqual(out.count('aria-current="page"'), 1)
        current = out.split('aria-current="page"')[1].split("</button>")[0]
        self.assertIn(">Stats<", current)

    def test_extra_links(self):
        links = ["<a onclick=\"pycmd('decks')\">Decks</a>", "<a onclick=\"pycmd('myaddon')\">My <b>Add-on</b></a>"]
        self.assertEqual(shell.extra_toolbar_links(links), [("myaddon", "My Add-on")])


if __name__ == "__main__":
    unittest.main()
