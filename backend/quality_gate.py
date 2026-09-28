"""
Layer 2 — Quality gate.

Pure logic, no network calls. Checks a raw prediction question for the
three things that most commonly cause disputed/unresolvable markets:

1. A clear deadline / resolution date
2. A checkable source (a URL, or a named verifiable source)
3. Unambiguous binary (yes/no) phrasing

Fully unit-testable in isolation (see tests/test_quality_gate.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_URL_RE = re.compile(r"https?://\S+")

# Improved deadline detector with support for ISO dates, various date formats,
# month names, and relative deadlines like "end of 2026"
_MONTHS = (
    r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?"
    r"|sep(t(ember)?)?|oct(ober)?|nov(ember)?|dec(ember)?"
)
_DEADLINE_HINTS = re.compile(
    r"\b(by|before|on|until|through)\s+(the\s+)?"
    r"("
    r"\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?"
    r"|\d{1,2}(st|nd|rd|th)?\s+(" + _MONTHS + r")\b"
    r"|(" + _MONTHS + r")\b"
    r"|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|end\s+of\s+(the\s+)?(day|week|month|year|quarter|\d{4})|eod|eow|eom|eoy"
    r")",
    re.IGNORECASE,
)

_NAMED_SOURCE_HINTS = re.compile(
    r"\b(according to|per|source:|via)\b", re.IGNORECASE
)

_BINARY_HINTS = re.compile(r"^\s*will\b.*\?", re.IGNORECASE)
_AMBIGUOUS_HINTS = re.compile(
    r"\b(maybe|kind of|sort of|probably|roughly|around|approximately)\b",
    re.IGNORECASE,
)


@dataclass
class CheckResult:
    passed: bool
    message: str


@dataclass
class QualityGateResult:
    deadline: CheckResult
    source: CheckResult
    binary: CheckResult

    @property
    def passed(self) -> bool:
        return self.deadline.passed and self.source.passed and self.binary.passed

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": {
                "deadline": {"passed": self.deadline.passed, "message": self.deadline.message},
                "source": {"passed": self.source.passed, "message": self.source.message},
                "binary": {"passed": self.binary.passed, "message": self.binary.message},
            },
        }


def check_deadline(question: str) -> CheckResult:
    if _DEADLINE_HINTS.search(question):
        return CheckResult(True, "Deadline found.")
    return CheckResult(
        False,
        "No clear deadline detected. Add a specific date or 'by <day/date>'.",
    )


def check_source(question: str, source_field: str | None = None) -> CheckResult:
    # A structured `sources_of_truth` field (e.g. entered separately in the Mini App)
    # always wins over trying to parse one out of free text.
    # Note: source_field can be a string (single source) or we handle the first item if it's from sources_of_truth
    if source_field and (_URL_RE.search(source_field) or len(str(source_field).strip()) > 0):
        return CheckResult(True, "Source provided.")
    if _URL_RE.search(question) or _NAMED_SOURCE_HINTS.search(question):
        return CheckResult(True, "Source reference found in question text.")
    return CheckResult(
        False,
        "No checkable source detected. Add a URL or name a specific, "
        "verifiable source (e.g. 'per official results at <site>').",
    )


def check_binary(question: str) -> CheckResult:
    if _AMBIGUOUS_HINTS.search(question):
        return CheckResult(
            False,
            "Question contains hedging language (e.g. 'probably', 'around'). "
            "Rephrase as a strict yes/no outcome.",
        )
    if _BINARY_HINTS.match(question.strip()):
        return CheckResult(True, "Phrased as a clear yes/no question.")
    return CheckResult(
        False,
        "Rephrase as a direct yes/no question, e.g. 'Will X happen by <date>?'",
    )


def run_quality_gate(question: str, source_field: str | None = None) -> QualityGateResult:
    return QualityGateResult(
        deadline=check_deadline(question),
        source=check_source(question, source_field),
        binary=check_binary(question),
    )
