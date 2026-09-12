from django.contrib import admin

from .models import AccessLog, Document, DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_required', 'order')
    list_editable = ('is_required', 'order')
    ordering = ('order',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'document_type', 'status', 'reviewer', 'submitted_at', 'reviewed_at')
    list_filter = ('status', 'document_type')
    search_fields = ('student__username', 'student__email')
    readonly_fields = ('storage_path', 'original_filename', 'content_type', 'file_size')


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('document', 'accessed_by', 'accessed_at')
    readonly_fields = ('document', 'accessed_by', 'accessed_at')

    def has_add_permission(self, request):
        return False