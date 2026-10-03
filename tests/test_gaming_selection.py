"""Gaming topics, actions and saved choices use independently reviewed catalog IDs."""
import copy
import unittest

from premium_emoji.catalog import catalog_data, parse_catalog
from premium_emoji.profiles import palette
from premium_emoji.profile_validation import validate_profile
from premium_emoji.selection import search
from premium_emoji.query import query_plan


class GamingSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = catalog_data(parse_catalog(), {})
        cls.by_id = {item['id']: item for item in cls.data['items']}

    def test_controller_play_and_dice_are_distinct_roles(self):
        for query, expected in [('геймпад', '6023852878597200124'),
                                ('начать игру', '5807414083388971488'),
                                ('настольные игры', '6021391505854306270')]:
            with self.subTest(query=query):
                result = search(self.data, query, pack='sfsymbols')
                self.assertEqual(result['candidates'][0]['id'], expected)
                self.assertEqual(result['decision'], 'matched')
        self.assertNotIn('board_game', self.by_id['6026021317390637493']['intents'])

    def test_game_names_do_not_become_ui_features_or_play_actions(self):
        plan = query_plan('Counter-Strike')
        self.assertEqual(plan['games'], ['counter_strike'])
        self.assertEqual(plan['features'], [])
        self.assertEqual(plan['terms'], [])
        self.assertNotIn('counter', self.by_id['5431628883352895287']['features'])
        self.assertNotIn('play', query_plan('PlayStation')['intents'])

    def test_known_topics_require_item_evidence_not_category_or_pack_name(self):
        wrong = copy.deepcopy(self.by_id['6021621630202027944'])
        wrong['search'] += ' minecraft GameIcons игры'
        wrong['pack'] = 'GameIcons'
        limited = {**self.data, 'items': [wrong]}
        result = search(limited, 'Майнкрафт')
        self.assertEqual(result['decision'], 'no_match')
        self.assertEqual(result['count'], 0)
        result = search(self.data, 'Майнкрафт', pack='GameIcons', include_special=True)
        self.assertTrue(all('minecraft' in item['games'] for item in result['candidates']))

    def test_negated_and_multiple_games_are_handled_as_whole_entities(self):
        plan = query_plan('Майнкрафт без Доты')
        self.assertEqual(plan['games'], ['minecraft'])
        self.assertEqual(plan['excluded_games'], ['dota'])
        for query in ['не CS2', 'without Counter-Strike', 'без Доты']:
            result = search(self.data, query, limit=1000)
            excluded = set(result['query']['excluded_games'])
            self.assertTrue(excluded)
            self.assertTrue(all(not excluded & set(item['games']) for item in result['candidates']))
        result = search(self.data, 'Майнкрафт и Дота')
        self.assertEqual(result['decision'], 'needs_clarification')
        self.assertIn('multiple_games', result['query']['warnings'])

    def test_game_context_does_not_force_a_logo_into_an_interface_action(self):
        for query, expected in [('Minecraft инвентарь', '6021621630202027944'),
                                ('CS2 начать игру', '5807414083388971488')]:
            result = search(self.data, query, pack='sfsymbols')
            self.assertEqual(result['query']['game_mode'], 'context')
            self.assertEqual(result['candidates'][0]['id'], expected)
        self.assertEqual(search(self.data, 'Майнкрафт', pack='sfsymbols')['decision'], 'no_match')

    def test_complete_interface_palette_stays_in_one_pack_and_keeps_bindings(self):
        roles = ['play', 'controller', 'board_game', 'inventory', 'reward', 'achievement',
                 'leaderboard', 'tournament', 'quest', 'health', 'currency', 'victory', 'defeat', 'settings']
        result = palette(self.data, roles, style='minimal', pack='sfsymbols')
        self.assertEqual(result['missing_roles'], [])
        profile = result['profile']
        self.assertEqual({saved['pack'] for saved in profile['roles'].values()}, {'sfsymbols'})
        self.assertEqual(validate_profile(self.data, profile), [])
        again = palette(self.data, roles, profile=profile)
        self.assertEqual(again['profile']['roles'], profile['roles'])
        self.assertTrue(all(item['pack'] == 'sfsymbols' for item in search(self.data, 'инвентарь', profile=profile)['candidates']))

    def test_previously_reviewed_controller_and_medal_bindings_remain_valid(self):
        profile = palette(self.data, ['legacy_play', 'legacy_ranking'], style='minimal', pack='sfsymbols',
                          role_queries={'legacy_play': 'кнопка играть', 'legacy_ranking': 'рейтинг игроков'},
                          bindings={'legacy_play': '6023852878597200124', 'legacy_ranking': '6021577980449396555'})['profile']
        profile['catalog_version'] = 'fd2a2da25b01185b'
        self.assertEqual(validate_profile(self.data, profile), [])
        again = palette(self.data, list(profile['roles']), profile=profile)
        self.assertEqual(again['profile']['roles'], profile['roles'])
        queried = search(self.data, 'кнопка играть', profile=profile)
        self.assertEqual(queried['candidates'][0]['id'], '6023852878597200124')
        self.assertTrue(queried['profile_context']['catalog_changed'])

    def test_explicit_topic_palette_uses_one_game_icon_pack(self):
        queries = {'minecraft': 'Майнкрафт', 'hearthstone': 'Хартстоун', 'dota': 'Дота', 'cs2': 'CS2', 'wow': 'WoW'}
        result = palette(self.data, list(queries), style='brand', pack='GameIcons', role_queries=queries)
        self.assertEqual(result['missing_roles'], [])
        self.assertEqual({role['pack'] for role in result['profile']['roles'].values()}, {'GameIcons'})
        self.assertEqual(validate_profile(self.data, result['profile']), [])

    def test_previously_reviewed_rating_star_is_not_replaced_by_a_new_trophy(self):
        profile = palette(self.data, ['player_ranking'], style='minimal', pack='pictograms_adaptive',
                          role_queries={'player_ranking': 'рейтинг игроков'},
                          bindings={'player_ranking': '5195351131693278899'})['profile']
        profile['catalog_version'] = 'fd2a2da25b01185b'
        self.assertEqual(validate_profile(self.data, profile), [])
        again = palette(self.data, list(profile['roles']), profile=profile)
        self.assertEqual(again['profile']['roles'], profile['roles'])


if __name__ == '__main__':
    unittest.main()
