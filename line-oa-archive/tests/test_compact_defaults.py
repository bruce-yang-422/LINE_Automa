import json
import unittest

import app
import chat_notes
import template_packs
from oa_fixture import CHANNEL
import test_recipients as fixtures


class CompactDefaultsTests(unittest.TestCase):
    setUp = fixtures.RecipientTests.setUp

    def test_small_defaults_and_consistent_template_categories(self):
        pack = template_packs.PRESET_PACKS['universal']
        templates = pack['case_templates'] + pack['note_templates']
        self.assertEqual(len(templates), 6)
        self.assertEqual(len(chat_notes.DEFAULT_CATEGORIES), 4)
        self.assertEqual(len(chat_notes.DEFAULT_TAGS), 8)
        self.assertEqual(set(pack['note_types']), {c['name'] for c in chat_notes.DEFAULT_CATEGORIES})
        for template in templates:
            self.assertIn(template['category_name'], pack['note_types'])
            self.assertTrue(set(template['defaults'].get('tags', [])) <= {t['name'] for t in chat_notes.DEFAULT_TAGS})



if __name__ == '__main__':
    unittest.main()
