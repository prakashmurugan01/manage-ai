from .aws_service import AwsHostingService
from .cloudflare_service import CloudflareHostingService
from .netlify_service import NetlifyHostingService
from .vercel_service import VercelHostingService


SERVICES = {
    "aws": AwsHostingService,
    "aws_s3": AwsHostingService,
    "aws_cloudfront": AwsHostingService,
    "cloudflare": CloudflareHostingService,
    "dns": CloudflareHostingService,
    "netlify": NetlifyHostingService,
    "vercel": VercelHostingService,
}


def get_service(provider, user=None):
    try:
        cls = SERVICES[str(provider).lower()]
    except KeyError as exc:
        from .base_service import ProviderConnectionError

        raise ProviderConnectionError("Provider is not connected to an API service.", code="unsupported_provider", status_code=404) from exc
    return cls(user=user)
