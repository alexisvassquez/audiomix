# AudioMIX
# audio/ai/training/schemas.py

# Shared data contracts for AudioMIX AI modules.
# These dataclasses give the AI pipeline a consistent vocab so that:
#  1. extractors return structured feats
#  2. inference returns structured predictions
#  3. planners/runtime consume structured recommendations

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# structured audio feats extracted from a source track
# will be adjusted over time to match real outputs
# e.g., tempo, spectral contrast, mfccs, etc.
@dataclass
class AudioFeatures:
    source_path: str
    bpm: Optional[float] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None

    # these are just examples - real features will depend on the extractor module
    rms: Optional[float] = None
    zero_crossing_rate: Optional[float] = None
    centroid_mean: Optional[float] = None
    rolloff_mean: Optional[float] = None

    # these are placeholders for more complex features that may be added later
    mfcc_mean: List[float] = field(default_factory=list)
    spectral_contrast_mean: List[float] = field(default_factory=list)

    # raw unstructured features for flexibility - not all modules will use these
    raw_features: Dict[str, Any] = field(default_factory=dict)

# output from predict_eq / inference_engine
# e.g., "boost_bass", "cut_mids", "brighten_highs"
@dataclass
class EQPrediction:
    labels: List[str] = field(default_factory=list)
    confidences: Dict[str, float] = field(default_factory=dict)
    model_name: Optional[str] = None
    notes: Optional[str] = None

# output from mood_classifier
# e.g., mellow, hyper, angry, energetic, ambient
@dataclass
class MoodPrediction:
    label: str = "unknown"
    confidence: float = 0.0
    scores: Dict[str, float] = field(default_factory=dict)
    model_name: Optional[str] = None

# output from audience_listener - live energy sensing
# e.g., calm, rising, hype, overload
@dataclass
class AudienceState:
    energy_level: str = "unknown"
    loudness: Optional[float] = None
    confidence: float = 0.0
    notes: Optional[str] = None

# generic performance recommendation for lighting behavior
# does not assume LED hardware (yet)
# TODO: hook into HAL (hardware abstraction layer)
# lighting, visuals, FX, automation, or stage control
@dataclass
class PerformanceSuggestion:
    mood: str
    intensity: float
    bpm: Optional[float] = None
    color_hint: Optional[str] = None
    effect_hint: Optional[str] = None
    eq_hint: Optional[str] = None
    reason: str = ""

# IR compiled AudioScript emitted by AI decision layer
# this is the final output consumed by the runtime lighting orchestrator
@dataclass
class AudioScriptSuggestion:
    script: str
    summary: str

# final combined recommendation produced by the decision_engine
# this is the main data contract consumed by the runtime orchestrator
@dataclass
class AIRecommendation:
    audio_features: Optional[AudioFeatures] = None
    eq_prediction: Optional[EQPrediction] = None
    mood_prediction: Optional[MoodPrediction] = None
    audience_state: Optional[AudienceState] = None
    performance_suggestion: Optional[PerformanceSuggestion] = None
    audioscript_suggestion: Optional[AudioScriptSuggestion] = None

    # this is a catch-all for the overall confidence of the recommendation,
    #  which can be used by the runtime to decide how aggressively to apply changes
    overall_confidence: float = 0.0
    confidence_tier: str = "low"
    notes: List[str] = field(default_factory=list)
