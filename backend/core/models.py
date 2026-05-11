from django.db import models
from pgvector.django import VectorField


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Matter(TimeStampedModel):
    class DraftingStatus(models.TextChoices):
        OPEN = "open", "Open"
        REVIEW = "review", "In review"
        CLOSED = "closed", "Closed"

    external_id = models.CharField(max_length=128, blank=True, db_index=True)
    client_name = models.CharField(max_length=255)
    court = models.CharField(max_length=255, blank=True)
    county = models.CharField(max_length=128, default="Cuyahoga")
    office_location = models.CharField(max_length=128, blank=True)
    eviction_ground = models.CharField(max_length=128, blank=True)
    subsidy_status = models.CharField(max_length=128, blank=True)
    problem_codes = models.JSONField(default=list, blank=True)
    special_problem_codes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=32, choices=DraftingStatus.choices, default=DraftingStatus.OPEN)

    def __str__(self) -> str:
        return f"{self.client_name} ({self.external_id or self.pk})"


class CaseNote(TimeStampedModel):
    matter = models.ForeignKey(Matter, related_name="case_notes", on_delete=models.CASCADE)
    author = models.CharField(max_length=255, blank=True)
    note_date = models.DateField(null=True, blank=True)
    body = models.TextField()

    def __str__(self) -> str:
        return f"Note for {self.matter_id}"


class EvidenceItem(TimeStampedModel):
    class EvidenceType(models.TextChoices):
        NOTE = "note", "Case note"
        DOCUMENT = "document", "Document"
        CLIENT_STATEMENT = "client_statement", "Client statement"
        DOCKET = "docket", "Docket"
        OTHER = "other", "Other"

    matter = models.ForeignKey(Matter, related_name="evidence", on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    evidence_type = models.CharField(max_length=32, choices=EvidenceType.choices, default=EvidenceType.OTHER)
    source_uri = models.CharField(max_length=500, blank=True)
    summary = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.title


class Fact(TimeStampedModel):
    class VerificationStatus(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    matter = models.ForeignKey(Matter, related_name="facts", on_delete=models.CASCADE)
    text = models.TextField()
    source_evidence = models.ForeignKey(EvidenceItem, null=True, blank=True, on_delete=models.SET_NULL)
    source_note = models.ForeignKey(CaseNote, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=32, choices=VerificationStatus.choices, default=VerificationStatus.PROPOSED)

    def __str__(self) -> str:
        return self.text[:80]


class LegalSource(TimeStampedModel):
    class SourceType(models.TextChoices):
        CASE = "case", "Case law"
        STATUTE = "statute", "Statute"
        TREATISE = "treatise", "Treatise"
        LOCAL_RULE = "local_rule", "Local rule"
        TEMPLATE = "template", "Template language"
        INTERNAL = "internal", "Internal guidance"

    title = models.CharField(max_length=500)
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    citation = models.CharField(max_length=255, blank=True)
    jurisdiction = models.CharField(max_length=128, default="Ohio")
    county = models.CharField(max_length=128, blank=True)
    court = models.CharField(max_length=255, blank=True)
    precedential_weight = models.CharField(max_length=128, blank=True)
    topic_tags = models.JSONField(default=list, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    superseded_date = models.DateField(null=True, blank=True)
    review_status = models.CharField(max_length=64, default="needs_review")
    source_url = models.URLField(blank=True)

    def __str__(self) -> str:
        return self.citation or self.title


class SourceChunk(TimeStampedModel):
    source = models.ForeignKey(LegalSource, related_name="chunks", on_delete=models.CASCADE)
    chunk_index = models.PositiveIntegerField(default=0)
    text = models.TextField()
    embedding_model = models.CharField(max_length=128, blank=True)
    embedding = VectorField(dimensions=1536, null=True, blank=True)

    class Meta:
        ordering = ["source_id", "chunk_index"]
        unique_together = ("source", "chunk_index")

    def __str__(self) -> str:
        return f"{self.source_id}:{self.chunk_index}"


class DraftGoal(TimeStampedModel):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    default_block_order = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.name


class CandidateGround(TimeStampedModel):
    class SelectionStatus(models.TextChoices):
        PROPOSED = "proposed", "Proposed"
        SELECTED = "selected", "Selected"
        REJECTED = "rejected", "Rejected"
        NEEDS_FACTS = "needs_facts", "Needs facts"

    matter = models.ForeignKey(Matter, related_name="candidate_grounds", on_delete=models.CASCADE)
    goal = models.ForeignKey(DraftGoal, related_name="candidate_grounds", on_delete=models.CASCADE)
    code = models.SlugField()
    title = models.CharField(max_length=255)
    rationale = models.TextField(blank=True)
    elements = models.JSONField(default=list, blank=True)
    supporting_fact_ids = models.JSONField(default=list, blank=True)
    missing_fact_questions = models.JSONField(default=list, blank=True)
    authority_source_ids = models.JSONField(default=list, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    status = models.CharField(max_length=32, choices=SelectionStatus.choices, default=SelectionStatus.PROPOSED)

    class Meta:
        unique_together = ("matter", "goal", "code")

    def __str__(self) -> str:
        return self.title


class DraftPackage(TimeStampedModel):
    class PackageStatus(models.TextChoices):
        PLANNING = "planning", "Planning"
        DRAFTING = "drafting", "Drafting"
        REVIEW = "review", "Review"
        EXPORTED = "exported", "Exported"

    matter = models.ForeignKey(Matter, related_name="draft_packages", on_delete=models.CASCADE)
    goal = models.ForeignKey(DraftGoal, related_name="draft_packages", on_delete=models.PROTECT)
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=PackageStatus.choices, default=PackageStatus.PLANNING)
    selected_ground_ids = models.JSONField(default=list, blank=True)
    approved_fact_ids = models.JSONField(default=list, blank=True)
    approved_source_ids = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.title


class DraftBlock(TimeStampedModel):
    class BlockKind(models.TextChoices):
        CAPTION = "caption", "Caption"
        OPENING = "opening", "Opening"
        FACTS = "facts", "Facts"
        ARGUMENT = "argument", "Argument"
        PRAYER = "prayer", "Prayer"
        SIGNATURE = "signature", "Signature"
        CUSTOM = "custom", "Custom"

    package = models.ForeignKey(DraftPackage, related_name="blocks", on_delete=models.CASCADE)
    kind = models.CharField(max_length=32, choices=BlockKind.choices)
    order = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["package_id", "order", "id"]

    def __str__(self) -> str:
        return self.title


class AITrace(TimeStampedModel):
    class TraceKind(models.TextChoices):
        MATTER_AUDIT = "matter_audit", "Matter audit"
        RETRIEVAL = "retrieval", "Retrieval"
        DRAFT_PLAN = "draft_plan", "Draft plan"
        DRAFT_GENERATION = "draft_generation", "Draft generation"
        VALIDATION = "validation", "Validation"

    matter = models.ForeignKey(Matter, related_name="ai_traces", on_delete=models.CASCADE)
    package = models.ForeignKey(DraftPackage, related_name="ai_traces", null=True, blank=True, on_delete=models.CASCADE)
    trace_kind = models.CharField(max_length=32, choices=TraceKind.choices)
    provider = models.CharField(max_length=128, default="stub")
    model = models.CharField(max_length=128, blank=True)
    prompt_version = models.CharField(max_length=128, blank=True)
    input_snapshot = models.JSONField(default=dict, blank=True)
    output_snapshot = models.JSONField(default=dict, blank=True)
    reviewer_notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.trace_kind} for {self.matter_id}"
