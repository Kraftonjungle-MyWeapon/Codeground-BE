from pydantic import BaseModel


class WinRateResponse(BaseModel):
    win: int
    loss: int
    draw: int
    win_rate: float
