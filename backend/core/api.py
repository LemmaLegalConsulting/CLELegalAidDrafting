from __future__ import annotations

from datetime import datetime
from typing import Any

import logging
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, NinjaAPI, Schema

logger = logging.getLogger(__name__)

from .models import CandidateGround, DraftBlock, DraftGoal, DraftPackage, Fact, LegalSource, Matter
from .services import audit_matter_for_goal, create_demo_matter, create_draft_package, ensure_seed_data

api = NinjaAPI(title="Cleveland Legal Aid", version="0.1.0")


class MatterIn(Schema):
    external_id: str = ""
    client_name: str
    court: str = ""
    county: str = "Cuyahoga"
    office_location: str = ""
    eviction_ground: str = ""
    subsidy_status: str = ""
    problem_codes: list[str] = []
    special_problem_codes: list[str] = []


class MatterOut(ModelSchema):
    class Meta:
        model = Matter
        fields = [
            "id",
            "external_id",
            "client_name",
            "court",
            "county",
            "office_location",
            "eviction_ground",
            "subsidy_status",
            "problem_codes",
            "special_problem_codes",
            "status",
            "created_at",
            "updated_at",
        ]


class FactOut(Schema):
    id: int
    matter_id: int
    text: str
    status: str
    created_at: datetime


class GoalOut(ModelSchema):
    class Meta:
        model = DraftGoal
        fields = ["id", "code", "name", "description", "default_block_order"]


class CandidateGroundOut(Schema):
    id: int
    matter_id: int
    goal_id: int
    code: str
    title: str
    rationale: str
    elements: list[str]
    supporting_fact_ids: list[int]
    missing_fact_questions: list[str]
    authority_source_ids: list[int]
    confidence: float
    status: str
    created_at: datetime
    updated_at: datetime


class CandidateGroundPatch(Schema):
    status: str


class DraftPackageCreate(Schema):
    goal_code: str = "motion_to_dismiss"
    selected_ground_ids: list[int] = []


class DraftPackageOut(Schema):
    id: int
    matter_id: int
    goal_id: int
    title: str
    status: str
    selected_ground_ids: list[int]
    approved_fact_ids: list[int]
    approved_source_ids: list[int]
    created_at: datetime
    updated_at: datetime


class DraftBlockOut(Schema):
    id: int
    package_id: int
    kind: str
    order: int
    title: str
    content: str
    metadata: dict[str, Any]
    enabled: bool
    updated_at: datetime


class DraftBlockPatch(Schema):
    title: str | None = None
    content: str | None = None
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


class LegalSourceOut(ModelSchema):
    class Meta:
        model = LegalSource
        fields = [
            "id",
            "title",
            "source_type",
            "citation",
            "jurisdiction",
            "county",
            "court",
            "precedential_weight",
            "topic_tags",
            "review_status",
            "source_url",
        ]


class PackageDetailOut(Schema):
    package: DraftPackageOut
    blocks: list[DraftBlockOut]


@api.get("/health")
def health(request):
    return {"status": "ok"}


@api.post("/seed")
def seed(request):
    logger.info("Seeding demo data")
    ensure_seed_data()
    matter = create_demo_matter()
    logger.info(f"Created demo matter with ID: {matter.id}")
    return {"matter_id": matter.id}


@api.get("/goals", response=list[GoalOut])
def list_goals(request):
    ensure_seed_data()
    return DraftGoal.objects.all().order_by("name")


@api.get("/matters", response=list[MatterOut])
def list_matters(request):
    return Matter.objects.all().order_by("-updated_at")


@api.post("/matters", response=MatterOut)
def create_matter(request, payload: MatterIn):
    return Matter.objects.create(**payload.model_dump())


@api.get("/matters/{matter_id}", response=MatterOut)
def get_matter(request, matter_id: int):
    return get_object_or_404(Matter, id=matter_id)


@api.get("/matters/{matter_id}/facts", response=list[FactOut])
def list_facts(request, matter_id: int):
    return Fact.objects.filter(matter_id=matter_id).order_by("id")


@api.post("/matters/{matter_id}/audit", response=list[CandidateGroundOut])
def audit_matter(request, matter_id: int, goal_code: str = "motion_to_dismiss"):
    ensure_seed_data()
    matter = get_object_or_404(Matter, id=matter_id)
    goal = get_object_or_404(DraftGoal, code=goal_code)
    return audit_matter_for_goal(matter, goal)


@api.get("/matters/{matter_id}/candidate-grounds", response=list[CandidateGroundOut])
def list_candidate_grounds(request, matter_id: int, goal_code: str | None = None):
    queryset = CandidateGround.objects.filter(matter_id=matter_id)
    if goal_code:
        queryset = queryset.filter(goal__code=goal_code)
    return queryset.order_by("-confidence", "title")


@api.patch("/candidate-grounds/{ground_id}", response=CandidateGroundOut)
def update_candidate_ground(request, ground_id: int, payload: CandidateGroundPatch):
    ground = get_object_or_404(CandidateGround, id=ground_id)
    ground.status = payload.status
    ground.save(update_fields=["status", "updated_at"])
    return ground


@api.post("/matters/{matter_id}/draft-packages", response=DraftPackageOut)
def create_package(request, matter_id: int, payload: DraftPackageCreate):
    ensure_seed_data()
    matter = get_object_or_404(Matter, id=matter_id)
    goal = get_object_or_404(DraftGoal, code=payload.goal_code)
    return create_draft_package(matter, goal, payload.selected_ground_ids)


@api.get("/matters/{matter_id}/draft-packages", response=list[DraftPackageOut])
def list_packages(request, matter_id: int):
    return DraftPackage.objects.filter(matter_id=matter_id).order_by("-updated_at")


@api.get("/draft-packages/{package_id}", response=PackageDetailOut)
def get_package(request, package_id: int):
    package = get_object_or_404(DraftPackage, id=package_id)
    return {"package": package, "blocks": list(package.blocks.all())}


@api.patch("/draft-blocks/{block_id}", response=DraftBlockOut)
def update_block(request, block_id: int, payload: DraftBlockPatch):
    block = get_object_or_404(DraftBlock, id=block_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(block, field, value)
    block.save()
    return block


@api.get("/legal-sources", response=list[LegalSourceOut])
def list_legal_sources(request, q: str | None = None):
    queryset = LegalSource.objects.all().order_by("title")
    if q:
        queryset = queryset.filter(title__icontains=q)
    return queryset[:50]
