from kyanbasu.task_types import PayloadTask, RuntimePayload, TaskRecord


def build_payload(tasks: list[TaskRecord]) -> RuntimePayload:
    short_by_uuid = {t["uuid"]: t["short"] for t in tasks}
    edges = []
    parent_current_deps = {}
    children_map = {}
    for t in tasks:
        p = short_by_uuid[t["uuid"]]
        for d in (t.get("depends") or []):
            if d in short_by_uuid:
                c = short_by_uuid[d]
                edges.append({"from": p, "to": c})
                parent_current_deps.setdefault(p, set()).add(c)
                children_map.setdefault(c, set()).add(p)
    payload_tasks: list[PayloadTask] = [
        {
            "uuid": t["uuid"],
            "short": t["short"],
            "desc": t["desc"],
            "project": t["project"],
            "tags": t["tags"],
            "has_depends": bool(t["depends"]),
            "due": t["due"],
        }
        for t in tasks
    ]
    return {
        "tasks": payload_tasks,
        "graph": {
            "edges": edges,
            "parent_current_deps": {k: sorted(v) for k, v in parent_current_deps.items()},
            "child_to_parents": {k: sorted(v) for k, v in children_map.items()},
        },
    }
