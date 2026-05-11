from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from .models import AITrace, CandidateGround, DraftBlock, DraftGoal, DraftPackage, Fact, LegalSource, Matter


MOTION_TO_DISMISS_BLOCKS = [
    "caption",
    "opening",
    "facts",
    "argument",
    "prayer",
    "signature",
]


GROUND_LIBRARY = [
    {
        "code": "defective_three_day_notice",
        "title": "Defective three-day notice",
        "elements": [
            "Landlord served a notice before filing the eviction.",
            "The notice did not comply with Ohio three-day notice requirements.",
            "The defect prejudices or defeats the eviction filing.",
        ],
        "signals": ["nonpayment", "3-day", "three day", "notice"],
        "questions": [
            "When did the tenant receive the three-day notice?",
            "Does the notice include the required statutory language?",
            "Was the eviction filed before the notice period expired?",
        ],
    },
    {
        "code": "failure_to_cure_notice",
        "title": "Failure to provide required cure notice",
        "elements": [
            "The eviction is based on an alleged lease or rule violation.",
            "The tenant was entitled to notice and an opportunity to cure.",
            "The landlord did not provide a compliant cure notice or filed too soon.",
        ],
        "signals": ["rule violation", "lease violation", "30 day", "cure"],
        "questions": [
            "What lease term or rule does the landlord claim was violated?",
            "Did the tenant receive a written cure notice?",
            "What did the tenant do to cure the alleged violation?",
        ],
    },
    {
        "code": "subsidized_housing_procedure",
        "title": "Subsidized housing procedural violation",
        "elements": [
            "The tenancy is subsidized or federally regulated.",
            "The landlord had additional procedural obligations.",
            "The landlord did not satisfy those obligations before filing.",
        ],
        "signals": ["section 8", "subsidized", "public housing", "voucher", "hud"],
        "questions": [
            "What subsidy program applies to the tenant's housing?",
            "Did the landlord send required notices to the housing authority?",
            "Was the tenant offered any required grievance or conference process?",
        ],
    },
    {
        "code": "retaliation",
        "title": "Retaliatory eviction",
        "elements": [
            "The tenant engaged in protected activity.",
            "The landlord knew about the protected activity.",
            "The eviction followed closely enough to support retaliation.",
        ],
        "signals": ["complaint", "code enforcement", "repair", "retaliation"],
        "questions": [
            "What protected activity did the tenant take?",
            "When did the landlord learn about it?",
            "What happened between the protected activity and the eviction filing?",
        ],
    },
]


@dataclass(frozen=True)
class AuditSnapshot:
    matter_text: str
    fact_text: str
    note_text: str

    @property
    def combined(self) -> str:
        return " ".join([self.matter_text, self.fact_text, self.note_text]).lower()


def ensure_seed_data() -> None:
    DraftGoal.objects.get_or_create(
        code="motion_to_dismiss",
        defaults={
            "name": "Motion to dismiss",
            "description": "Structured eviction motion workflow with candidate grounds, facts, authorities, and draft blocks.",
            "default_block_order": MOTION_TO_DISMISS_BLOCKS,
        },
    )
    DraftGoal.objects.get_or_create(
        code="advice_letter",
        defaults={
            "name": "Advice letter",
            "description": "Client-facing legal advice letter assembled from approved facts and sources.",
            "default_block_order": ["opening", "facts", "argument", "prayer", "signature"],
        },
    )


def create_demo_matter() -> Matter:
    ensure_seed_data()
    matter = Matter.objects.create(
        external_id="DEMO-001",
        client_name="Demo Tenant",
        court="Cleveland Municipal Court",
        county="Cuyahoga",
        office_location="Cleveland",
        eviction_ground="Nonpayment of rent",
        subsidy_status="Unknown",
        problem_codes=["nonpayment", "notice"],
        special_problem_codes=["possible_defective_notice"],
    )
    evidence = matter.evidence.create(
        title="Initial intake summary",
        evidence_type="client_statement",
        summary="Tenant reports receiving a three-day notice after asking for repairs. The filing date may be too soon.",
    )
    Fact.objects.create(
        matter=matter,
        text="Tenant reports receiving a three-day notice shortly before the eviction was filed.",
        source_evidence=evidence,
    )
    Fact.objects.create(
        matter=matter,
        text="Tenant asked the landlord to make repairs before the eviction notice.",
        source_evidence=evidence,
    )
    matter.case_notes.create(
        author="MVP seed",
        body="Potential notice defect and possible retaliation facts. Need actual notice and docket dates.",
    )
    return matter


def _snapshot_for_matter(matter: Matter) -> AuditSnapshot:
    facts = " ".join(matter.facts.values_list("text", flat=True))
    notes = " ".join(matter.case_notes.values_list("body", flat=True))
    matter_text = " ".join(
        [
            matter.eviction_ground,
            matter.subsidy_status,
            " ".join(matter.problem_codes),
            " ".join(matter.special_problem_codes),
        ]
    )
    return AuditSnapshot(matter_text=matter_text, fact_text=facts, note_text=notes)


@transaction.atomic
def audit_matter_for_goal(matter: Matter, goal: DraftGoal) -> list[CandidateGround]:
    snapshot = _snapshot_for_matter(matter)
    combined = snapshot.combined
    created: list[CandidateGround] = []

    for ground in GROUND_LIBRARY:
        signal_hits = [signal for signal in ground["signals"] if signal in combined]
        if not signal_hits:
            continue

        confidence = min(Decimal("0.95"), Decimal("0.45") + Decimal("0.10") * len(signal_hits))
        selected_facts = list(
            matter.facts.filter(text__icontains=signal_hits[0]).values_list("id", flat=True)[:3]
        )
        candidate, _ = CandidateGround.objects.update_or_create(
            matter=matter,
            goal=goal,
            code=ground["code"],
            defaults={
                "title": ground["title"],
                "rationale": f"Matched case signals: {', '.join(signal_hits)}.",
                "elements": ground["elements"],
                "supporting_fact_ids": selected_facts,
                "missing_fact_questions": ground["questions"],
                "authority_source_ids": list(
                    LegalSource.objects.filter(topic_tags__contains=[ground["code"]]).values_list("id", flat=True)[:5]
                ),
                "confidence": confidence,
            },
        )
        created.append(candidate)

    AITrace.objects.create(
        matter=matter,
        trace_kind=AITrace.TraceKind.MATTER_AUDIT,
        prompt_version="stub-audit-v1",
        input_snapshot={
            "matter": matter.id,
            "goal": goal.code,
            "problem_codes": matter.problem_codes,
            "special_problem_codes": matter.special_problem_codes,
        },
        output_snapshot={"candidate_ground_ids": [candidate.id for candidate in created]},
    )
    return created


@transaction.atomic
def create_draft_package(matter: Matter, goal: DraftGoal, selected_ground_ids: list[int] | None = None) -> DraftPackage:
    selected_ground_ids = selected_ground_ids or list(
        matter.candidate_grounds.filter(goal=goal, status=CandidateGround.SelectionStatus.SELECTED).values_list("id", flat=True)
    )
    title = f"{goal.name} - {matter.client_name}"
    package = DraftPackage.objects.create(
        matter=matter,
        goal=goal,
        title=title,
        selected_ground_ids=selected_ground_ids,
        approved_fact_ids=list(matter.facts.filter(status=Fact.VerificationStatus.VERIFIED).values_list("id", flat=True)),
    )

    block_titles = {
        "caption": "Caption",
        "opening": "Opening paragraph",
        "facts": "Facts",
        "argument": "Argument",
        "prayer": "Prayer for relief",
        "signature": "Signature block",
    }
    for index, kind in enumerate(goal.default_block_order or MOTION_TO_DISMISS_BLOCKS):
        DraftBlock.objects.create(
            package=package,
            kind=kind if kind in DraftBlock.BlockKind.values else DraftBlock.BlockKind.CUSTOM,
            order=index,
            title=block_titles.get(kind, kind.replace("_", " ").title()),
            content=_starter_block_content(kind, matter, selected_ground_ids),
        )

    AITrace.objects.create(
        matter=matter,
        package=package,
        trace_kind=AITrace.TraceKind.DRAFT_PLAN,
        prompt_version="stub-draft-plan-v1",
        input_snapshot={"selected_ground_ids": selected_ground_ids},
        output_snapshot={"draft_package_id": package.id, "block_count": package.blocks.count()},
    )
    return package


def _starter_block_content(kind: str, matter: Matter, selected_ground_ids: list[int]) -> str:
    if kind == "opening":
        return f"Tenant moves this Court to dismiss the eviction complaint for the reasons set forth below."
    if kind == "facts":
        facts = matter.facts.all()[:5]
        return "\n".join(f"- {fact.text}" for fact in facts) or "[Add verified facts here.]"
    if kind == "argument":
        grounds = CandidateGround.objects.filter(id__in=selected_ground_ids)
        if not grounds:
            return "[Select grounds to generate argument sections.]"
        return "\n\n".join(f"{ground.title}\n{ground.rationale}" for ground in grounds)
    if kind == "prayer":
        return "Tenant respectfully requests that the Court dismiss the eviction complaint and grant any further relief that is just."
    if kind == "caption":
        return f"[Caption for {matter.court or 'Court'} / {matter.client_name}]"
    if kind == "signature":
        return "[Advocate signature block]"
    return ""

