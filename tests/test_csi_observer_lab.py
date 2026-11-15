"""Measurement definitions only; real owned-PTY cases are retained separately."""
import unittest

from medir_observador_pty import sampled_cpu_percent,SCENARIOS


class MeasurementDefinitionTests(unittest.TestCase):
    def test_cpu_is_sample_delta_over_wall_time_not_including_later_audit(self):
        self.assertIsNone(sampled_cpu_percent([]))
        self.assertIsNone(sampled_cpu_percent([dict(cpu_ns=1,elapsed_s=0)]))
        native=[dict(cpu_ns=10_000_000,elapsed_s=1),dict(cpu_ns=40_000_000,elapsed_s=2)]
        observer=[dict(cpu_ns=100,wall_ns=1_000),dict(cpu_ns=125,wall_ns=2_000)]
        self.assertAlmostEqual(sampled_cpu_percent(native),3)
        self.assertAlmostEqual(sampled_cpu_percent(observer),2.5)

    def test_slow_consumer_has_explicit_distinct_view_limits(self):
        self.assertFalse(SCENARIOS['baseline']['observer'])
        self.assertEqual(SCENARIOS['normal']['max_rows'],300)
        self.assertEqual(SCENARIOS['slow']['max_rows'],8)
        self.assertGreater(SCENARIOS['slow']['consumer_interval_s'],SCENARIOS['normal']['consumer_interval_s'])


if __name__=='__main__':unittest.main()
