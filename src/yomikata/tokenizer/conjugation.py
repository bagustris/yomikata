"""Human-readable descriptions of Sudachi's conjugated-form tags.

Sudachi's part-of-speech tuple encodes the grammatical form a token was
conjugated into (e.g. the continuative "-i" stem vs. the imperative) as a
terse Japanese label at index 5. This module translates the common ones
into short English descriptions, purely from data :class:`Token` already
carries -- no extra dictionary lookup or grammar engine involved.
"""

from __future__ import annotations

import logging

from yomikata.tokenizer.sudachi import Token

logger = logging.getLogger(__name__)

#: Sudachi conjugated-form tags (``part_of_speech[5]``) mapped to a short
#: English description. Covers the forms observed from the bundled
#: SudachiDict on inflected verbs, adjectives, and auxiliaries; "*" (the
#: tag for uninflected words) is deliberately unlisted. A tag missing
#: here is logged at debug level by :func:`describe_conjugation`, so new
#: tags introduced by a dictionary update are discoverable rather than
#: silently dropped.
_CONJUGATED_FORM_LABELS: dict[str, str] = {
    "終止形-一般": "conclusive form",
    "終止形-撥音便": "conclusive form (sound change)",
    "連体形-一般": "attributive form",
    "連体形-撥音便": "attributive form (sound change)",
    "連体形-補助": "attributive form",
    "連用形-一般": "continuative form",
    "連用形-促音便": "continuative form (sound change)",
    "連用形-撥音便": "continuative form (sound change)",
    "連用形-イ音便": "continuative form (sound change)",
    "連用形-ウ音便": "continuative form (sound change)",
    "未然形-一般": "irrealis form",
    "未然形-撥音便": "irrealis form (sound change)",
    "未然形-サ": "irrealis form",
    "未然形-セ": "irrealis form",
    "仮定形-一般": "hypothetical form (-ba)",
    "仮定形-融合": "hypothetical form (-ba)",
    "命令形": "imperative form",
    "意志推量形": "volitional form",
    "語幹-一般": "stem form",
    "語幹-サ": "stem form",
}


def describe_conjugation(token: Token) -> str | None:
    """Describe how a token's surface form was conjugated from its lemma.

    Args:
        token: A tokenized unit, as produced by
            :class:`~yomikata.tokenizer.sudachi.SudachiTokenizer`.

    Returns:
        A short description, e.g. ``"continuative form of 食べる"``, or
        None if the surface already matches the dictionary form, or
        Sudachi did not report a recognized conjugated-form tag.
    """
    if token.surface == token.dictionary_form:
        return None
    if len(token.part_of_speech) < 6:
        return None
    tag = token.part_of_speech[5]
    label = _CONJUGATED_FORM_LABELS.get(tag)
    if label is None:
        if tag != "*":
            logger.debug(
                "Unmapped Sudachi conjugated-form tag %r for surface %r (lemma %r)",
                tag,
                token.surface,
                token.dictionary_form,
            )
        return None
    return f"{label} of {token.dictionary_form}"
