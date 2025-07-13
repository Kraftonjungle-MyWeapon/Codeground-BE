from typing import Dict, List
from collections import defaultdict
from fastapi import WebSocket
import asyncio


game_rooms: Dict[int, List[WebSocket]] = defaultdict(list)
game_user_map: Dict[int, List[int]] = {}
ready_status: Dict[int, Dict[int, bool]] = defaultdict(dict)
disconnected_users: Dict[int, int] = {}

# ---------------------------------------------------------------------------
# Timer management utilities
# ---------------------------------------------------------------------------

end_times: Dict[int, float] = {}
is_paused: Dict[int, bool] = defaultdict(lambda: False)
remaining_time_on_pause: Dict[int, float] = {}
timer_tasks: Dict[int, asyncio.Task] = {}
