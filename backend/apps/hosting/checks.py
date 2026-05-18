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
    }
    for provider, names in checks.items():
        missing = [name for name in names if not getattr(settings, name, "")]
        if missing:
            warnings.append(
                Warning(
                    f"{provider} API NOT CONNECTED: missing {', '.join(missing)}.",
                    hint="Set provider tokens in backend/.env. Alias names like VERCEL_TOKEN and NETLIFY_TOKEN are supported.",
                    id=f"hosting.W{len(warnings) + 1:03d}",
                )
            )
    return warnings
