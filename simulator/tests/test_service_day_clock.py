"""
Tests for ServiceDayClock.

BUILD 4 Phase 5B: Dedicated scheduling clock managing simulated service-day time.
"""

from datetime import date
import unittest

from simulator.service_day.clock import ServiceDayClock


class TestServiceDayClock(unittest.TestCase):

    def test_clock_initialization(self):
        clock = ServiceDayClock(
            service_date=date(2026, 9, 3),
            start_time_of_day="06:30:00",
            timezone_name="Asia/Kolkata",
            time_multiplier=2.0,
        )
        self.assertEqual(clock.service_date, date(2026, 9, 3))
        self.assertEqual(clock.time_multiplier, 2.0)
        self.assertFalse(clock.paused)
        self.assertFalse(clock.completed)
        self.assertEqual(clock.elapsed_service_seconds, 0.0)
        self.assertEqual(clock.time_string, "06:30:00")
        self.assertIn("2026-09-03T06:30:00", clock.isoformat)

    def test_clock_progression(self):
        clock = ServiceDayClock(
            service_date=date(2026, 9, 3),
            start_time_of_day="05:00:00",
            timezone_name="Asia/Kolkata",
            time_multiplier=1.0,
        )
        # Advance 60 real seconds at 1x
        sim_adv = clock.advance(60.0)
        self.assertEqual(sim_adv, 60.0)
        self.assertEqual(clock.elapsed_service_seconds, 60.0)
        self.assertEqual(clock.time_string, "05:01:00")

        # Set multiplier to 5x and advance 10 real seconds -> 50 sim seconds
        clock.set_multiplier(5.0)
        sim_adv2 = clock.advance(10.0)
        self.assertEqual(sim_adv2, 50.0)
        self.assertEqual(clock.elapsed_service_seconds, 110.0)
        self.assertEqual(clock.time_string, "05:01:50")

    def test_clock_pause_resume(self):
        clock = ServiceDayClock(
            service_date=date(2026, 9, 3),
            start_time_of_day="05:00:00",
            timezone_name="Asia/Kolkata",
        )
        clock.pause()
        self.assertTrue(clock.paused)
        self.assertEqual(clock.advance(10.0), 0.0)
        self.assertEqual(clock.elapsed_service_seconds, 0.0)

        clock.resume()
        self.assertFalse(clock.paused)
        self.assertEqual(clock.advance(10.0), 10.0)
        self.assertEqual(clock.elapsed_service_seconds, 10.0)

    def test_clock_reset_and_complete(self):
        clock = ServiceDayClock(
            service_date=date(2026, 9, 3),
            start_time_of_day="05:00:00",
            timezone_name="Asia/Kolkata",
        )
        clock.advance(120.0)
        self.assertEqual(clock.elapsed_service_seconds, 120.0)

        clock.reset()
        self.assertEqual(clock.elapsed_service_seconds, 0.0)
        self.assertEqual(clock.time_string, "05:00:00")

        clock.mark_completed()
        self.assertTrue(clock.completed)
        self.assertEqual(clock.advance(60.0), 0.0)


if __name__ == "__main__":
    unittest.main()
