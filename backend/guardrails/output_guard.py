import re

from fastapi import HTTPException, status

MIN_ANSWER_LENGTH = 20
CITATION_PATTERN = re.compile(r'\[\d+\]')

_VALIDATION_ERROR = "Response validation failed. Please rephrase your question."


def check_output(answer: str, has_sources: bool) -> None:
    """
    Raise HTTPException 422 if:
    - answer is empty or too short
    - sources were retrieved but answer contains no citation [N]
    """
    if not answer or len(answer) < MIN_ANSWER_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_VALIDATION_ERROR,
        )
    if has_sources and not CITATION_PATTERN.search(answer):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_VALIDATION_ERROR,
        )
