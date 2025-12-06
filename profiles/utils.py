def get_user_status(user):
    try:
        if user.role in ["admin", "journalist"]:
            return user.adminjournalistprofile.status
        elif user.role == "user":
            return user.profile.status
    except Exception:
        return "active"  # fallback
    return "active"