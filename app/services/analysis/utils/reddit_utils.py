"""
Reddit utility functions for analyzing Reddit presence.
This module contains helper functions for Reddit API interactions and scoring.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List

def log_scale(value: float, max_pts: float, k: float) -> float:
    """
    Logarithmic scaling with soft cap @ k.
    :param value: raw value
    :param max_pts: maximum points cap
    :param k: value that maps to a significant portion of max_pts
    """
    if value <= 0:
        return 0.0
    return min(max_pts, math.log(value + 1, k + 1) * max_pts)

def exp_decay(hours_since: float, half_life_h: float, max_pts: float) -> float:
    """
    Exponential decay: full points at t=0, half at half_life.
    :param hours_since: hours since the event
    :param half_life_h: half-life in hours
    :param max_pts: maximum points
    """
    if hours_since is None:
        return 0.0
    return max_pts * math.exp(-hours_since * math.log(2) / half_life_h) 