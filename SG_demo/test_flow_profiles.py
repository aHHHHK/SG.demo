"""Run with the project's Python/Ipopt environment: python test_flow_profiles.py."""
import unittest

from twin_baseline import BaselineTwin


class FlowProfileParity(unittest.TestCase):
    def assert_same_physics(self, left, right):
        for group in ('state', 'inputs', 'derived', 'controls'):
            for key, expected in left[group].items():
                actual = right[group][key]
                if isinstance(expected, (int, float)):
                    self.assertAlmostEqual(expected, actual, places=8, msg=f'{group}.{key}')
                else:
                    self.assertEqual(expected, actual)
        self.assertEqual(left['time'], right['time'])
        self.assertEqual(left['model_time'], right['model_time'])
        for key in ('duration', 'step_time', 'display_trim'):
            self.assertEqual(left['provenance'][key], right['provenance'][key])

    def test_initial_playback_actions_and_restore(self):
        qs = BaselineTwin('SG_qs', .01)
        level = BaselineTwin('SG_level', .01)
        self.assert_same_physics(qs.snapshot(), level.snapshot())
        self.assertEqual(level.snapshot()['model_time'], 99)
        self.assertEqual(level.snapshot()['derived']['delta_level'], 0)
        # Cross the original scripted step: neither profile should step by itself.
        for _ in range(53):
            left, right = qs.step({}), level.step({})
            self.assert_same_physics(left, right)
            self.assertEqual(right['inputs']['q_f'], 250)
            self.assertEqual(right['inputs']['q_s'], 250)
        for action, ratio in (('qs', .001), ('qf', -.001), ('temp', .001)):
            self.assert_same_physics(qs.action(action, ratio), level.action(action, ratio))
            self.assert_same_physics(qs.step({}), level.step({}))
        self.assert_same_physics(qs.action('restore'), level.action('restore'))
        self.assertEqual(level.profile, 'SG_level')
        self.assertEqual(level.snapshot()['derived']['delta_level'], 0)
        self.assertEqual(level.snapshot()['time'], 0)
        self.assertEqual(len(level.history), 1)


if __name__ == '__main__':
    unittest.main()
