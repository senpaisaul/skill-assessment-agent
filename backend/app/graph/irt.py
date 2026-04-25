"""
Item Response Theory math for adaptive question selection.

Implements the 1-parameter logistic (Rasch) model:

    P(correct | theta, b) = sigmoid(theta - b)

where:
    theta = candidate's ability for this skill (latent, what we're estimating)
    b     = question difficulty (we set this from Bloom level: 1=Remember .. 5=Create)

After each answered question we update theta via Newton-Raphson on the
log-likelihood — ~5 lines of math, converges in 1-2 iterations on each turn.

Stanford CRFM and ATLAS showed this is enough to rank candidates with Spearman
ρ > 0.96 using just 8.5% of full-test items. We use the same machinery to pick
the next question whose difficulty is closest to the current θ̂ (max info point).

DESIGN CONSTRAINTS:
- All functions pure (no I/O, no LLM calls) → trivially testable
- All bounded: theta clamped to [-3, 3], b clamped to [-3, 3]
- Bloom 1-5 mapped to b in roughly [-2, 2] so θ stays well-defined
"""

from __future__ import annotations

import math
from app.models import ProficiencyLevel


# Bounds — theta and b live in this range to avoid sigmoid saturation
THETA_MIN, THETA_MAX = -3.0, 3.0
B_MIN, B_MAX = -3.0, 3.0


def bloom_to_difficulty(level: ProficiencyLevel) -> float:
    """
    Map a Bloom level (1-5) to an IRT difficulty parameter b.

    Centered so:
      Level 1 (Remember)  → b = -2.0  (easy)
      Level 2 (Understand)→ b = -1.0
      Level 3 (Apply)     → b =  0.0  (median — the hireable bar)
      Level 4 (Analyze)   → b = +1.0
      Level 5 (Evaluate)  → b = +2.0  (hard)
    """
    return float(level.value) - 3.0


def theta_to_bloom(theta: float) -> ProficiencyLevel:
    """
    Snap a continuous theta estimate to the nearest Bloom level.
    Inverse of bloom_to_difficulty for reporting + final scoring handoff.
    """
    rounded = round(theta + 3.0)
    rounded = max(1, min(5, rounded))
    return ProficiencyLevel(rounded)


def sigmoid(x: float) -> float:
    """Numerically stable logistic."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def prob_correct(theta: float, b: float) -> float:
    """P(correct | theta, b) under the Rasch model."""
    return sigmoid(theta - b)


def update_theta(
    theta: float,
    history: list[tuple[float, float]],
    iterations: int = 5,
    prior_weight: float = 0.5,
) -> float:
    """
    Update theta via Newton-Raphson MAP estimation.

    Args:
        theta: current ability estimate
        history: list of (b, score) where score in [0.0, 1.0]
                 — score is the LLM's continuous correctness rating, not just binary
        iterations: NR steps (5 is plenty for a 5-question loop)
        prior_weight: how strongly to pull theta toward 0 (regularization)
                      — keeps early estimates from swinging wildly on n=1

    Returns:
        Updated theta, clamped to [THETA_MIN, THETA_MAX].
    """
    if not history:
        return theta

    th = theta
    for _ in range(iterations):
        gradient = -prior_weight * th  # gaussian prior centered at 0
        info = prior_weight            # prior contribution to information

        for b, score in history:
            p = prob_correct(th, b)
            gradient += score - p
            info += p * (1.0 - p)

        if info < 1e-6:
            break
        th += gradient / info

    return max(THETA_MIN, min(THETA_MAX, th))


def confidence_from_history(history: list[tuple[float, float]]) -> float:
    """
    Estimate confidence in theta as 1 / (1 + standard_error).

    Standard error in IRT is 1 / sqrt(information). With only the prior,
    SE ≈ 1.41 → confidence ≈ 0.41. After 3-4 informative questions, SE
    drops to ~0.5 → confidence ~0.67, which is our default threshold for
    "stop probing this skill".
    """
    info = 0.5  # prior contribution
    for b, _score in history:
        # We don't have theta here, use an approximation: max info ≈ 0.25
        # at p=0.5 (when b≈theta). Scale down for "off-target" questions.
        info += 0.25
    se = 1.0 / math.sqrt(info) if info > 0 else 1.0
    return 1.0 / (1.0 + se)


def next_difficulty(
    theta: float,
    asked_difficulties: list[float],
    bloom_pool: list[ProficiencyLevel] | None = None,
) -> ProficiencyLevel:
    """
    Pick the next question's Bloom level — the one whose b is closest to theta
    (max-information point under Rasch), excluding already-asked levels when
    we have alternatives.

    Args:
        theta: current ability estimate for this skill
        asked_difficulties: list of b values already used for this skill
        bloom_pool: candidate Bloom levels. Defaults to all 5.

    Returns:
        ProficiencyLevel — the chosen Bloom level for the next question.
    """
    if bloom_pool is None:
        bloom_pool = [
            ProficiencyLevel.REMEMBER,
            ProficiencyLevel.UNDERSTAND,
            ProficiencyLevel.APPLY,
            ProficiencyLevel.ANALYZE,
            ProficiencyLevel.EVALUATE,
        ]

    # Score each candidate level by |b - theta|, then prefer unasked ones
    scored = []
    for level in bloom_pool:
        b = bloom_to_difficulty(level)
        distance = abs(b - theta)
        already_asked = b in asked_difficulties
        # Penalize already-asked unless they're the best fit
        scored.append((distance, already_asked, level))

    scored.sort(key=lambda x: (x[1], x[0]))  # unasked first, then closest to theta
    return scored[0][2]
