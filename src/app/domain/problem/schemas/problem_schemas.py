from typing import List, Optional
from pydantic import BaseModel


class TestCase(BaseModel):
    input: str
    output: str
    description: Optional[str] = None
    visibility: str


class ProblemCreateRequest(BaseModel):
    title: str
    description: str
    input_format: str
    output_format: str
    time_limit_milliseconds: str
    memory_limit_kilobytes: str
    difficulty: str
    category: List[str]
    constraints: Optional[str] = None
    languages: List[str]
    test_cases: List[TestCase]


class ProblemCreateResponse(BaseModel):
    problem_id: int


CATEGORY_INDEX_TO_NAME = [
    "implementation",
    "simulation",
    "dp",
    "greedy",
    "stack",
    "queue",
    "string",
    "math",
    "geometry",
    "sorting",
    "binary-search",
    "parametric-search",
    "graph",
    "dfs",
    "bfs",
    "shortest-path"
]