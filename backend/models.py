"""Shared request/response models for the FastAPI backend."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QuestionSubmission(BaseModel):
    question: str
    resolution_rule: str
    sources_of_truth: list[str]
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    resolution_time: Optional[int] = None


class QuoteRequest(QuestionSubmission):
    pass


class BuildRequest(BaseModel):
    create_id: str
    wallet: str


class RegisterRequest(BaseModel):
    create_id: str
    signature: str
