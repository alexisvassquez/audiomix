# audiomix
# AudioMIX
# audio/ai/core/decision_engine.py

# Combines outputs from existing AudioMIX AI modules
#  into one structured recommendation
# It consumes structured predictions, build
#  recommendations, and generates
#  inspectable AudioScript (AS)
# The logic is designed to be refined over time with
#  more data and insights.

from __future__ import annotations
from typing import List, Optional

from audio.ai.schemas import (
    AIRecommendation,
    AudioFeatures,
    AudioScriptSuggestion,
    AudienceState,
    EQPrediction,
    MoodPrediction,
    PerformanceSuggestion,
)
from audio.ai.core.confidence import (
    combine_confidences,
    confidence_tier,
    pick_best_label,
    top_confidence,
)

# pick best EQ label from prediction output
# prefers confidences if present, 
# otherwise falls back to first label
def _choose_primary_eq_label(eq_prediction: Optional[EQPrediction]) -> Optional[str]:
    """
    Returns the most relevant EQ label based on the prediction output.
    Prefers the label with the highest confidence if confidences are available,
    otherwise falls back to the first label in the list."""
    if eq_prediction is None:
        return None

    if eq_prediction.confidences:
        return pick_best_label(eq_prediction.confidences)

    if eq_prediction.labels:
        return eq_prediction.labels[0]
    return None

# lightweight policy layer for translating predictions
#  into a generic effect hint.
# hardware agnostic until I can get the hardware
#  abstraction layer up and running
def _derive_effect_hint(
    mood_label: str,
    bpm: Optional[float],
    audience_state: Optional[AudienceState],
) -> str:
    """
    Derives a generic effect hint based on mood, tempo, and audience energy.
    This is a simple policy layer that translates structured predictions into a hardware-agnostic effect suggestion.
    """
    mood = (mood_label or "unknown").lower()
    audience_energy = (
        audience_state.energy_level.lower()
        if audience_state and audience_state.energy_level
        else "unknown"
    )

    # prioritize audience energy for effect
    #  suggestions, as it's more dynamic and
    #  performance-relevant
    if audience_energy in {"hype", "high", "rising"}:
        if bpm is not None and bpm >= 120:
            return "pulse"
        return "build"

    # fallback to mood-based suggestions if audience
    #  energy is not strongly indicative
    if mood in {"energetic", "euphoria", "hype"}:
        return "pulse"
    if mood in {"dark", "tense", "angry"}:
        return "sweep"
    if mood in {"calm", "relaxed", "ambient"}:
        return "fade"

    return "blend"

# optional abstract color suggestion
# mapped to HAL later
def _derive_color_hint(mood_label: str) -> Optional[str]:
    """
    Derives a color hint based on the mood label. 
    This is a simple mapping that can be expanded with more moods and corresponding colors. 
    The returned color is a generic descriptor that can be translated to specific hardware capabilities in the future.
    """
    mood = (mood_label or "unknown").lower()

    if mood in {"energetic", "euphoric", "hype"}:
        return "neon_pink"
    if mood in {"dark", "tense", "angry"}:
        return "deep_red"
    if mood in {"calm", "relaxed", "ambient"}:
        return "warm_amber"
    if mood in {"happy", "bright"}:
        return "gold"
    if mood in {"sad", "melancholic"}:
        return "electric_blue"

    return None

# convert prediction context into a generic
#  performance intensity [0.0, 1.0]
def _derive_intensity(
    mood_prediction: Optional[MoodPrediction],
    audience_state: Optional[AudienceState],
    audio_features: Optional[AudioFeatures],
) -> float:
    """
    Derives a performance intensity value between 0.0 
    and 1.0 based on mood, audience energy, and tempo. 
    This function uses a simple heuristic approach to combine different aspects of the prediction context into a single intensity metric that can guide performance decisions. 
    """
    intensity = 0.45

    if mood_prediction:
        mood = mood_prediction.label.lower()
        if mood in {"energetic", "euphoric", "hype"}:
            intensity += 0.25
        elif mood in {"dark", "tense", "angry"}:
            intensity += 0.15
        elif mood in {"calm", "relaxed", "ambient"}:
            intensity -= 0.10

        intensity += min(0.15, mood_prediction.confidence * 0.15)

    if audio_features and audio_features.bpm is not None:
        if audio_features.bpm >= 128:
            intensity += 0.10
        elif audio_features.bpm <= 85:
            intensity -= 0.05

    if audience_state:
        energy = audience_state.energy_level.lower()
        if energy in {"rising", "high", "hype"}:
            intensity += 0.10
        elif energy in {"overload"}:
            intensity -= 0.05
        elif energy in {"low", "quiet", "calm"}:
            intensity -= 0.05

    return max(0.0, min(1.0, round(intensity, 3)))

# create a hardware agnostic performance suggestion
#  from current prediction context
def build_performance_suggestion(
    mood_prediction: Optional[MoodPrediction],
    eq_prediction: Optional[EQPrediction],
    audience_state: Optional[AudienceState],
    audio_features: Optional[AudioFeatures],
) -> Optional[PerformanceSuggestion]:
    """
    Builds a PerformanceSuggestion object based on the current prediction context.
    This function synthesizes information from mood predictions, EQ predictions, audience state, and audio features to create a structured recommendation for performance adjustments. 
    The resulting PerformanceSuggestion includes a mood label, intensity level, effect hint, color hint, and EQ hint, along with a reason that explains the basis for the suggestion.
    """
    mood_label = mood_prediction.label if mood_prediction else "unknown"
    bpm = audio_features.bpm if audio_features else None
    eq_label = _choose_primary_eq_label(eq_prediction)

    intensity = _derive_intensity(
        mood_prediction=mood_prediction,
        audience_state=audience_state,
        audio_features=audio_features,
    )

    effect_hint = _derive_effect_hint(
        mood_label=mood_label,
        bpm=bpm,
        audience_state=audience_state,
    )

    color_hint = _derive_color_hint(mood_label)

    reason_parts: List[str] = [f"performance profile derived from mood '{mood_label}'"]

    # include key contextual factors in the reason for traceability
    if bpm is not None:
        reason_parts.append(f"tempo context {bpm:.2f} BPM")
    if eq_label:
        reason_parts.append(f"EQ hint '{eq_label}'")
    if audience_state:
        reason_parts.append(f"audience energy '{audience_state.energy_level}'")

    # the reason is a concatenation of all the factors
    #  that contributed to the suggestion, 
    #  for transparency and debugging
    return PerformanceSuggestion(
        mood=mood_label,
        intensity=intensity,
        effect_hint=effect_hint,
        color_hint=color_hint,
        eq_hint=eq_label,
        reason="; ".join(reason_parts),
    )

# emit a small inspectable AudioScript snippet from recommendations
# generic/conservative right now until I expand
# only emits current AS commands in runtime
def build_audioscript_suggestion(
    performance_suggestion: Optional[PerformanceSuggestion],
    mood_prediction: Optional[MoodPrediction],
    eq_prediction: Optional[EQPrediction],
    audio_features: Optional[AudioFeatures] = None,
) -> Optional[AudioScriptSuggestion]:
    """
    Builds an AudioScriptSuggestion based on the performance suggestion and current predictions.
    This function translates the structured performance suggestion and relevant predictions into a small snippet of AudioScript commands that can be executed by the performance engine. 
    The generated AudioScript is designed to be simple and focused on the most actionable insights, such as mood-based effects, EQ presets, and performance intensity adjustments. 
    The summary provides a human-readable explanation of the suggested actions for easy inspection and debugging.
    """
    lines: List[str] = []
    summary_parts: List[str] = []

    # map performance intensity to a generic "intensity" command in AudioScript
    if performance_suggestion and performance_suggestion.intensity is not None:
        intensity_value = int(round(performance_suggestion.intensity * 100))
        lines.append(f'intensity({intensity_value})')
        summary_parts.append(f"intensity @{intensity_value}%")
    if mood_prediction and mood_prediction.label != "unknown":
        lines.append(f'mood.set("{mood_prediction.label}")')
        summary_parts.append(f"mood '{mood_prediction.label}'")

    # if we have a clear EQ suggestion, include it as well
    eq_label = _choose_primary_eq_label(eq_prediction)
    if eq_label:
        lines.append(f'eq.preset("{eq_label}")')
        summary_parts.append(f"EQ preset '{eq_label}'")

    # if we have an effect hint, include it as well
    if performance_suggestion and performance_suggestion.effect_hint:
        lines.append(f'effect("{performance_suggestion.effect_hint}")')
        summary_parts.append(f"effect '{performance_suggestion.effect_hint}'")
    if performance_suggestion and performance_suggestion.color_hint:
        lines.append(f'glow("{performance_suggestion.color_hint}")')
        summary_parts.append(f"color '{performance_suggestion.color_hint}'")

    # if the effect hint is "pulse" and we have a BPM, include a tempo-synced pulse command
    if (
        performance_suggestion
        and performance_suggestion.effect_hint == "pulse"
        and audio_features
        and audio_features.bpm is not None
    ):
        bpm_value = int(round(audio_features.bpm))
        pulse_color = performance_suggestion.color_hint or "blue"
        lines.append(f'pulse("{pulse_color}", bpm={bpm_value})')
        summary_parts.append(f"pulse @{bpm_value} BPM")

    if not lines:
        return None

    return AudioScriptSuggestion(
        script="\n".join(lines),
        summary=" + ".join(summary_parts),
    )

# main entry point
# combines structured AI outputs into a single recommendation object
def build_ai_recommendation(
    audio_features: Optional[AudioFeatures] = None,
    mood_prediction: Optional[MoodPrediction] = None,
    eq_prediction: Optional[EQPrediction] = None,
    audience_state: Optional[AudienceState] = None,
) -> AIRecommendation:
    """Builds a comprehensive AIRecommendation by synthesizing audio features, mood predictions, EQ predictions, and audience state.
    This function serves as the main entry point for combining various AI module outputs into a single structured recommendation that can guide performance decisions and generate actionable AudioScript suggestions. 
    The resulting AIRecommendation includes all relevant inputs, the derived performance suggestion, the generated AudioScript suggestion, and a set of notes that explain the basis for the recommendations and provide context for debugging and refinement.
    """
    notes: List[str] = []
    confidence_inputs: List[float] = []

    # we can use the confidence scores from mood and EQ predictions as part of our overall confidence calculation for the recommendation
    if mood_prediction:
        confidence_inputs.append(mood_prediction.confidence)
        if mood_prediction.model_name:
            notes.append(f"Mood model: {mood_prediction.model_name}")

    # EQ confidence is less directly tied to a single label, 
    # but we can still extract the top confidence score
    # to include in our overall confidence calculation
    if eq_prediction:
        eq_conf = top_confidence(eq_prediction.confidences)
        confidence_inputs.append(eq_conf)
        if eq_prediction.model_name:
            notes.append(f"EQ model: {eq_prediction.model_name}")

    # audience state is more volatile and less directly tied to a confidence score,
    # but we can still include it as a factor in the overall confidence calculation
    if audience_state:
        confidence_inputs.append(audience_state.confidence)
        notes.append(f"Audience state: {audience_state.energy_level}")

    overall_conf = combine_confidences(confidence_inputs)
    tier = confidence_tier(overall_conf)

    # the performance suggestion is the core actionable insight that combines 
    # all the prediction context into a structured
    #  recommendation for how to adjust the performance
    performance_suggestion = build_performance_suggestion(
        mood_prediction=mood_prediction,
        eq_prediction=eq_prediction,
        audience_state=audience_state,
        audio_features=audio_features,
    )

    # the AudioScript suggestion translates the
    #  performance suggestion and relevant predictions
    #  into a concrete set of commands that can be
    #  executed by the performance engine, along with a
    #  human-readable summary for inspection and debugging
    audioscript_suggestion = build_audioscript_suggestion(
        performance_suggestion=performance_suggestion,
        mood_prediction=mood_prediction,
        eq_prediction=eq_prediction,
        audio_features=audio_features,
    )

    if audio_features and audio_features.bpm is not None:
        notes.append(f"Detected BPM: {audio_features.bpm:.2f}")

    notes.append(f"Overall confidence tier: {tier}")

    # the final recommendation object includes all the
    #  inputs, the derived performance suggestion, the
    #  generated AudioScript suggestion, and a set of
    #  notes that explain the basis for the
    #  recommendations and provide context for debugging and refinement
    return AIRecommendation(
        audio_features=audio_features,
        mood_prediction=mood_prediction,
        eq_prediction=eq_prediction,
        audience_state=audience_state,
        performance_suggestion=performance_suggestion,
        audioscript_suggestion=audioscript_suggestion,
        overall_confidence=overall_conf,
        confidence_tier=tier,
        notes=notes,
    )
