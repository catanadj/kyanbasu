from typing import TypedDict


class TaskRecord(TypedDict):
    uuid: str
    short: str
    desc: str
    project: str
    tags: list[str]
    depends: list[str]
    due: str | None


class PayloadTask(TypedDict):
    uuid: str
    short: str
    desc: str
    project: str
    tags: list[str]
    has_depends: bool
    due: str | None


class PayloadGraph(TypedDict):
    edges: list[dict[str, str]]
    parent_current_deps: dict[str, list[str]]
    child_to_parents: dict[str, list[str]]


class RuntimePayloadBase(TypedDict):
    tasks: list[PayloadTask]
    graph: PayloadGraph


class RuntimePayload(RuntimePayloadBase, total=False):
    workspace_id: str
