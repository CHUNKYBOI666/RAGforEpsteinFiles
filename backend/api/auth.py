# Anonymous device-id based identity for /api/chat and session endpoints.
# Reads X-Device-Id header; validates UUID format.

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status


def get_device_id(request: Request) -> str:
    """Extract and validate X-Device-Id header. Returns device_id string."""
    device_id = request.headers.get("X-Device-Id", "").strip()
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Device-Id header.",
        )
    try:
        UUID(device_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Device-Id: must be a valid UUID.",
        )
    return device_id


RequireDeviceId = Annotated[str, Depends(get_device_id)]
