from typing import Optional

from pydantic import BaseModel


class AccessTokenResponse(BaseModel):
    token_type: str = "Bearer"
    expires_in: int
    access_token: str
    refresh_token: Optional[str] = None
