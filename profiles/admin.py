from django.contrib import admin
from .models import Profile, AdminJournalistProfile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'status', 'date_of_birth', 'has_profile_picture')
    list_filter = ('status',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email')
    ordering = ('user__username',)
    
    def has_profile_picture(self, obj):
        return bool(obj.profile_picture)
    has_profile_picture.boolean = True
    has_profile_picture.short_description = 'Profile Picture?'

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(AdminJournalistProfile)
class AdminJournalistProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role_display', 'news_count', 'total_news_views', 'has_profile_picture')
    search_fields = ('user__username', 'user__email')
    ordering = ('user__username',)

    def role_display(self, obj):
        return obj.user.role
    role_display.short_description = 'Role'

    def has_profile_picture(self, obj):
        return bool(obj.profile_picture)
    has_profile_picture.boolean = True
    has_profile_picture.short_description = 'Profile Picture?'

    def news_count(self, obj):
        return obj.news_count
    news_count.short_description = 'Total News'

    def total_news_views(self, obj):
        return obj.total_news_views
    total_news_views.short_description = 'Total Views'
