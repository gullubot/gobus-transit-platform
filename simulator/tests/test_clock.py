"""
Tests for SimulationClock.
"""

from datetime import datetime, timezone
import unittest

from simulator.core.clock import SimulationClock


class TestClock(unittest.TestCase):

    def test_clock_tick_progression(self):
        start = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
        clock = SimulationClock(start_time=start, time_multiplier=1.0)

        self.assertEqual(clock.current_time, start)
        self.assertEqual(clock.elapsed_sim_seconds, 0.0)

        # Tick 1.0 real second
        t1 = clock.tick(1.0)
        self.assertEqual(clock.elapsed_real_seconds, 1.0)
        self.assertEqual(clock.elapsed_sim_seconds, 1.0)
        self.assertEqual(t1.second, 1)

    def test_clock_multiplier(self):
        start = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
        clock = SimulationClock(start_time=start, time_multiplier=10.0)

        # 2 real seconds = 20 simulated seconds
        t = clock.tick(2.0)
        self.assertEqual(clock.elapsed_real_seconds, 2.0)
        self.assertEqual(clock.elapsed_sim_seconds, 20.0)
        self.assertEqual(t.second, 20)

    def test_clock_pause_and_resume(self):
        start = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
        clock = SimulationClock(start_time=start, time_multiplier=1.0)

        clock.pause()
        clock.tick(5.0)
        self.assertEqual(clock.elapsed_sim_seconds, 0.0)
        self.assertEqual(clock.current_time, start)

        clock.resume()
        clock.tick(5.0)
        self.assertEqual(clock.elapsed_sim_seconds, 5.0)

    def test_clock_reset(self):
        start1 = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
        start2 = datetime(2026, 9, 3, 15, 0, 0, tzinfo=timezone.utc)
        clock = SimulationClock(start_time=start1)

        clock.tick(10.0)
        self.assertEqual(clock.elapsed_sim_seconds, 10.0)

        clock.reset(new_start_time=start2)
        self.assertEqual(clock.current_time, start2)
        self.assertEqual(clock.elapsed_sim_seconds, 0.0)

    def test_invalid_tick_raises_error(self):
        clock = SimulationClock()
        with self.assertRaises(ValueError):
            clock.tick(-1.0)


if __name__ == "__main__":
    unittest.main()
