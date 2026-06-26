# AudioMIX
# audio/ai/core/confidence.py

from __future__ import annotations
from typing import Dict, Iterable, Optional


# Confidence utilities for AudioMIX AI predictions.
# Keeps threshold logic centralized so every module
#  is not acting on its own interpretation of what
#  "high confidence" means.

# This module provides functions to:
# - Normalize confidence scores into a [0.0, 1.0] range
# - Map numeric confidence to named tiers (high, medium, low)
# - Determine if a prediction should be applied based on confidence
# - Combine multiple confidence scores into a single score
# - Extract the top confidence from a set of class predictions
HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.55

# normalize score into [0.0, 1.0]
def clamp_confidence(score: Optional[float]) -> float:
    """
    Clamps a confidence score to the range [0.0, 1.0]. If the score is None, returns 0.0.
    This function ensures that confidence scores are valid and can be safely compared against thresholds.
    """
    if score is None:
        return 0.0
    return max(0.0, min(1.0, float(score)))

# map numeric confidence to a named tier
def confidence_tier(score: Optional[float]) -> str:
    """
    Maps a numeric confidence score to a named tier: 'high', 'medium', or 'low'."""
    value = clamp_confidence(score)
    if value >= HIGH_CONFIDENCE:
        return "high"
    if value >= MEDIUM_CONFIDENCE:
        return "medium"
    return "low"

# True when a prediction is strong enough for auto/assertive recommendation
def should_apply(score: Optional[float], threshold: float = HIGH_CONFIDENCE) -> bool:
    """
    Determines if a prediction should be applied based
      on its confidence score and a specified threshold.
    By default, the threshold is set to HIGH_CONFIDENCE (0.80),
      meaning that only predictions with a confidence score of 0.80 or higher will be considered strong enough to apply.
    """
    return clamp_confidence(score) >= threshold

# simple average of valid confidences
# keeps behavior understandable + easy to debug
def combine_confidences(scores: Iterable[Optional[float]]) -> float:
    """
    Combines multiple confidence scores into a single
      score by averaging the valid (non-None) scores after clamping them to the [0.0, 1.0] range. If there are no valid scores, returns 0.0.
    This function allows for a simple aggregation of
      multiple confidence scores, providing an overall confidence level that can be used for decision-making in the AI system.
    """
    values = [clamp_confidence(score) for score in scores if score is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)

# return the strongest class confidence from a label->score mapping
def top_confidence(confidences: Dict[str, float]) -> float:
    """
    Returns the highest confidence score from a dictionary of label-to-confidence mappings. 
    If the dictionary is empty, returns 0.0.
    This function is useful for extracting the most
      confident prediction from a set of class predictions, allowing the AI system to focus on the strongest signal when making decisions based on multiple potential labels.
    """
    if not confidences:
        return 0.0
    return clamp_confidence(max(confidences.values()))

# return label w/ the highest confidence
def pick_best_label(confidences: Dict[str, float]) -> Optional[str]:
    """
    Returns the label with the highest confidence
      score from a dictionary of label-to-confidence mappings. If the dictionary is empty, returns None.
    This function is useful for determining which
      class label has the strongest confidence score, allowing the AI system (Juniper2.0) to select the most likely prediction when multiple labels are present. 
      By returning None for an empty dictionary, it also provides a clear indication that no valid predictions were available.
    """
    if not confidences:
        return None
    return max(confidences, key=lambda label: confidences[label])
