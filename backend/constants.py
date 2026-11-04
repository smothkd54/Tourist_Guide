"""
backend/constants.py
--------------------
Values shared by the runtime, the seed script and the tests.

Keeping them here avoids importing `backend.app` (which loads the TFLite
model) just to learn which classes are publishable.
"""

# Classes that exist only in the training split: so few photos survive that no
# validation image is left. They are masked at inference time so a model that
# never saw a validation example cannot confidently claim them.
UNVALIDATED_CLASSES = frozenset({
    "lashch_revenue_house",
    "tkachenko_revenue_house",
})

# Predictions below this are reported as "unknown" rather than as a guess.
CONFIDENCE_THRESHOLD = 0.35

# One model class covers two adjacent buildings: the training manifest for
# `kramer_estate` contains images of both kramer_mansion (114) and
# kramer_revenue_house (116). The class cannot honestly point at either one,
# so it points at the mansion as the representative record and the mapping is
# recorded in model_classes.mapping_note. Prediction keeps the class id so the
# top-5 stays truthful, but resolves the detail card to a real landmark.
CLASS_LANDMARK_ALIASES = {
    "kramer_estate": "kramer_mansion",
}

