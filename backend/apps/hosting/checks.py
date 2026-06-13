from django.conf import settings
from django.core.checks import Warning, register


@register()
def hosting_provider_credentials(app_configs, **kwargs):
    warnings = []
    checks = {
        "AWS": ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"),
        "Vercel": ("VERCEL_API_TOKEN",),
        "Netlify": ("NETLIFY_API_TOKEN",),
        "Cloudflare": ("CLOUDFLARE_API_TOKEN",),
        "DigitalOcean": ("DIGITALOCEAN_API_TOKEN",),
        "Hostinger": ("HOSTINGER_API_TOKEN",),
        "GoDaddy": ("GODADDY_API_KEY", "GODADDY_API_SECRET"),
        "Bluehost": ("BLUEHOST_API_KEY",),
        "SiteGround": ("SITEGROUND_API_TOKEN",),
        "BigRock": ("BIGROCK_API_KEY",),
        "cPanel": ("CPANEL_API_TOKEN",),
        "WHM": ("WHM_API_TOKEN",),
        "Plesk": ("PLESK_API_TOKEN",),
        "Railway": ("RAILWAY_API_TOKEN",),
        "Render": ("RENDER_API_KEY",),
        "Firebase": ("FIREBASE_SERVICE_ACCOUNT_JSON",),
        "Supabase": ("SUPABASE_ACCESS_TOKEN",),
    }
    for provider, names in checks.items():
        missing = [name for name in names if not getattr(settings, name, "")]
        if missing:
            warnings.append(
                Warning(
                    f"{provider} API NOT CONNECTED: missing {', '.join(missing)}.",
                    hint="Set provider tokens in backend/.env. Alias names like VERCEL_TOKEN, NETLIFY_TOKEN, AWS_ACCESS_KEY, and AWS_SECRET_KEY are supported.",
                    id=f"hosting.W{len(warnings) + 1:03d}",
                )
            )
    return warnings
