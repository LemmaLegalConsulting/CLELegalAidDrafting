from celery import shared_task

from .models import DraftGoal, Matter
from .services import audit_matter_for_goal, create_draft_package


@shared_task
def audit_matter_task(matter_id: int, goal_code: str = "motion_to_dismiss") -> list[int]:
    matter = Matter.objects.get(id=matter_id)
    goal = DraftGoal.objects.get(code=goal_code)
    candidates = audit_matter_for_goal(matter, goal)
    return [candidate.id for candidate in candidates]


@shared_task
def create_draft_package_task(matter_id: int, goal_code: str, selected_ground_ids: list[int] | None = None) -> int:
    matter = Matter.objects.get(id=matter_id)
    goal = DraftGoal.objects.get(code=goal_code)
    package = create_draft_package(matter, goal, selected_ground_ids)
    return package.id

