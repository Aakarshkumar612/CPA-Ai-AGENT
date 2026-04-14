"""
Unit tests for the PerformanceTimer.
"""

import time
import pytest

from utils.timer import PerformanceTimer, get_timer, reset_timer


class TestPerformanceTimer:
    def test_step_records_duration(self):
        timer = PerformanceTimer()
        with timer.step("parse"):
            time.sleep(0.05)
        assert timer.get_step_time("parse") >= 0.04

    def test_multiple_calls_accumulate(self):
        timer = PerformanceTimer()
        for _ in range(3):
            with timer.step("loop"):
                time.sleep(0.01)
        step = timer.steps["loop"]
        assert step.call_count == 3
        assert step.total_duration >= 0.02

    def test_avg_duration(self):
        timer = PerformanceTimer()
        with timer.step("s"):
            time.sleep(0.02)
        with timer.step("s"):
            time.sleep(0.04)
        avg = timer.steps["s"].avg_duration
        assert 0.02 <= avg <= 0.05

    def test_unknown_step_returns_none(self):
        timer = PerformanceTimer()
        assert timer.get_step_time("ghost") is None

    def test_log_stats_returns_string(self):
        timer = PerformanceTimer()
        with timer.step("x"):
            pass
        summary = timer.log_stats()
        assert "x" in summary
        assert "total" in summary.lower()

    def test_to_dict_structure(self):
        timer = PerformanceTimer()
        with timer.step("alpha"):
            time.sleep(0.01)
        d = timer.to_dict()
        assert "alpha" in d
        assert "total_duration" in d["alpha"]
        assert "call_count" in d["alpha"]
        assert d["alpha"]["call_count"] == 1

    def test_no_steps_log_stats(self):
        timer = PerformanceTimer()
        summary = timer.log_stats()
        assert "no steps" in summary.lower()


class TestGlobalTimer:
    def test_reset_gives_fresh_timer(self):
        t1 = get_timer()
        with t1.step("a"):
            pass
        t2 = reset_timer()
        assert "a" not in t2.steps

    def test_get_timer_returns_same_instance(self):
        reset_timer()
        t1 = get_timer()
        t2 = get_timer()
        assert t1 is t2
