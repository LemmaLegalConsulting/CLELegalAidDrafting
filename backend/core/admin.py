from django.contrib import admin

from .models import (
    AITrace,
    CandidateGround,
    CaseNote,
    DraftBlock,
    DraftGoal,
    DraftPackage,
    EvidenceItem,
    Fact,
    LegalSource,
    Matter,
    SourceChunk,
)


class DraftBlockInline(admin.TabularInline):
    model = DraftBlock
    extra = 0


@admin.register(Matter)
class MatterAdmin(admin.ModelAdmin):
    list_display = ("client_name", "external_id", "court", "county", "eviction_ground", "status")
    search_fields = ("client_name", "external_id", "court")
    list_filter = ("status", "county", "eviction_ground", "subsidy_status")


@admin.register(DraftPackage)
class DraftPackageAdmin(admin.ModelAdmin):
    list_display = ("title", "matter", "goal", "status", "updated_at")
    list_filter = ("status", "goal")
    inlines = [DraftBlockInline]


@admin.register(CandidateGround)
class CandidateGroundAdmin(admin.ModelAdmin):
    list_display = ("title", "matter", "goal", "status", "confidence")
    list_filter = ("status", "goal")
    search_fields = ("title", "rationale", "matter__client_name")


admin.site.register(CaseNote)
admin.site.register(EvidenceItem)
admin.site.register(Fact)
admin.site.register(LegalSource)
admin.site.register(SourceChunk)
admin.site.register(DraftGoal)
admin.site.register(DraftBlock)
admin.site.register(AITrace)

