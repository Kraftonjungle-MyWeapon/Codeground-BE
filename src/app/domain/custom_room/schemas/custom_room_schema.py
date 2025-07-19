from pydantic import BaseModel
from dataclasses import dataclass
from typing import Optional


class RoomCreateRequest(BaseModel):
    difficulty: str
    title: str
    use_language: str
    category: int


@dataclass
class UserState:
    user_id: int
    nickname: str
    mmr: int
    img_url : str
    ready: bool = False
    screen_sharing: bool = False
    screen_sharing_ready: bool = False
    connected: bool = False

@dataclass
class CustomRoom:
    room_id: int
    maker: Optional[UserState]
    user: Optional[UserState]
    difficulty: str
    category: int
    use_language: str
    title: str
    is_gaming: bool

@dataclass
class ResponseRoom:
    room_id: int
    maker: str
    user_cnt : int
    difficulty: str
    category: int
    use_language: str
    title: str
    is_gaming: bool