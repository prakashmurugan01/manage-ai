from apps.hosting.models import HostingLink
from apps.hosting.providers import ensure_default_providers, sync_aws_instances

from .base_service import BaseHostingService


class AwsHostingService(BaseHostingService):
    provider = HostingLink.Provider.AWS
    required_settings = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")

    def provider_aliases(self):
        return [HostingLink.Provider.AWS, HostingLink.Provider.AWS_S3, HostingLink.Provider.AWS_CLOUDFRONT]

    def get_projects(self):
        self.validate_connection()
        ensure_default_providers()
        sync_aws_instances()
        return [self.serialize_link(link) for link in self.local_links()]
