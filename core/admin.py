from django.contrib import admin
from .models import ResumeRequest, UserImage, UserProfile

class UserImageInline(admin.TabularInline):
    model = ResumeRequest.images.through
    extra = 1

@admin.register(ResumeRequest)
class ResumeRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'job_title', 'created_at', 'images_count']
    list_filter = ['created_at', 'user']
    inlines = [UserImageInline]
    def images_count(self, obj):
        return obj.images.count()
    images_count.short_description = 'Изображений'

@admin.register(UserImage)
class UserImageAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'uploaded_at']
    list_filter = ['uploaded_at', 'user']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'profession']

admin.site.site_header = "ResumeAI Administration"
