"""Validated interview contracts and deterministic scoring (no model/network calls)."""
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

SCORING_VERSION = "rubric-v1"
WEIGHTS = {"correctness": 50, "coverage": 30, "explanation": 20}
LEVEL_VALUES = {"none": 0, "limited": 25, "partial": 50, "good": 80, "excellent": 100}

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class Requirement(Contract):
    id: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=500)

class Rubric(Contract):
    requirements: list[Requirement] = Field(min_length=1, max_length=6)
    reference_approaches: list[str] = Field(max_length=5)
    error_criteria: list[str] = Field(max_length=5)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [item.id for item in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("Requirement IDs must be unique")
        for item in self.reference_approaches + self.error_criteria:
            if not item.strip():
                raise ValueError("Rubric entries cannot be blank")
        return self

class QuestionPackage(Contract):
    question: str = Field(min_length=1, max_length=4000)
    rubric: Rubric

class Dimension(Contract):
    level: Literal["none", "limited", "partial", "good", "excellent"]
    reason: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(max_length=4)

class RequirementAssessment(Contract):
    requirement_id: str = Field(min_length=1)
    status: Literal["met", "not_explained", "incorrect"]
    reason: str = Field(min_length=1, max_length=1000)
    evidence: list[str] = Field(max_length=4)

    @model_validator(mode="after")
    def evidence_for_claims(self):
        if self.status in {"met", "incorrect"} and not self.evidence:
            raise ValueError("Met/incorrect requirements need answer excerpts")
        return self

class ExplicitError(Contract):
    quote: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=1000)

class Evaluation(Contract):
    correctness: Dimension
    coverage: Dimension
    explanation: Dimension
    requirements: list[RequirementAssessment] = Field(min_length=1, max_length=6)
    explicit_errors: list[ExplicitError] = Field(max_length=6)
    answer_kind: Literal["substantive", "non_substantive", "empty"]
    reason: str = Field(min_length=1, max_length=1500)
    weakness: str = Field(min_length=1, max_length=1500)
    follow_up: str = Field(max_length=1000)

class ReportSummary(Contract):
    总体评价: str = Field(min_length=1, max_length=3000)
    优点: list[str] = Field(max_length=5)
    薄弱点: list[str] = Field(max_length=5)
    改进建议: list[str] = Field(max_length=5)

    @model_validator(mode="after")
    def nonblank_items(self):
        for item in self.优点 + self.薄弱点 + self.改进建议:
            if not item.strip():
                raise ValueError("Report entries cannot be blank")
        return self

def round_score(value):
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def validate_evaluation(data, rubric, answer):
    evaluation = Evaluation.model_validate(data)
    expected = {item.id for item in rubric.requirements}
    actual = [item.requirement_id for item in evaluation.requirements]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Evaluation must assess each requirement exactly once")
    if (evaluation.answer_kind == "empty") != (not answer.strip()):
        raise ValueError("Empty answer classification contradicts actual answer")
    dimensions = [getattr(evaluation, name) for name in WEIGHTS]
    excerpts = [quote for item in dimensions + evaluation.requirements for quote in item.evidence]
    excerpts += [item.quote for item in evaluation.explicit_errors]
    if any(not quote.strip() or quote not in answer for quote in excerpts):
        raise ValueError("Evidence must be an exact nonblank excerpt from the answer")
    if any(item.level != "none" and not item.evidence for item in dimensions):
        raise ValueError("Positive dimension levels need answer excerpts")
    if evaluation.answer_kind != "substantive" and any(item.level != "none" for item in dimensions):
        raise ValueError("Non-substantive answers must have zero dimension levels")
    if any(item.status == "incorrect" for item in evaluation.requirements) and not evaluation.explicit_errors:
        raise ValueError("Incorrect requirements need explicit error details")
    return evaluation

def calculate_score(evaluation):
    total = sum(WEIGHTS[name] * LEVEL_VALUES[getattr(evaluation, name).level] for name in WEIGHTS)
    return round_score(Decimal(total) / 100)

def average_score(history):
    if not history:
        raise ValueError("Cannot summarize an empty interview")
    scores = []
    for item in history:
        score = item["evaluation"]["score"]
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("History scores must be integers between 0 and 100")
        scores.append(score)
    return round_score(Decimal(sum(scores)) / len(scores))
