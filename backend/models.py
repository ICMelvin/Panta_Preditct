"""Shared request/response models for the FastAPI backend."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class QuestionSubmission(BaseModel):
    question: str
    source: Optional[str] = None
    deadline: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None


class QuoteRequest(QuestionSubmission):
    pass


class BuildRequest(BaseModel):
    quote_id: str
    creator_wallet: str


class RegisterRequest(BaseModel):
    build_id: str
    signed_transaction: str
