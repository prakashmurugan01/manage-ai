from django.db import migrations, models


HOSTED_PROJECT_PLATFORMS = [
    ("vercel", "Vercel"),
    ("railway", "Railway"),
    ("aws", "AWS"),
    ("s3", "AWS S3"),
    ("cloudfront", "AWS CloudFront"),
    ("netlify", "Netlify"),
    ("digitalocean", "DigitalOcean"),
    ("cloudflare", "Cloudflare"),
    ("cloudways", "Cloudways"),
    ("render", "Render"),
    ("firebase", "Firebase Hosting"),
    ("supabase", "Supabase"),
    ("github", "GitHub Deployments"),
    ("cpanel", "cPanel"),
    ("whm", "WHM"),
    ("plesk", "Plesk"),
    ("hostinger", "Hostinger"),
    ("scalahosting", "ScalaHosting"),
    ("siteground", "SiteGround"),
    ("bluehost", "Bluehost"),
    ("godaddy", "GoDaddy"),
    ("hostgator", "HostGator"),
    ("cyberin", "Cyberin"),
    ("hostingraja", "HostingRaja"),
    ("bigrock", "BigRock"),
    ("hosting_home", "Hosting Home"),
    ("custom", "Custom"),
]

PROVIDER_CHOICES = [
    ("aws", "AWS"),
    ("aws_s3", "AWS S3"),
    ("aws_cloudfront", "AWS CloudFront"),
    ("netlify", "Netlify"),
    ("digitalocean", "DigitalOcean"),
    ("cloudflare", "Cloudflare"),
    ("cloudways", "Cloudways"),
    ("railway", "Railway"),
    ("render", "Render"),
    ("firebase", "Firebase Hosting"),
    ("supabase", "Supabase"),
    ("github", "GitHub Deployments"),
    ("cpanel", "cPanel"),
    ("whm", "WHM"),
    ("plesk", "Plesk"),
    ("hostinger", "Hostinger"),
    ("scalahosting", "ScalaHosting"),
    ("siteground", "SiteGround"),
    ("bluehost", "Bluehost"),
    ("godaddy", "GoDaddy"),
    ("hostgator", "HostGator"),
    ("cyberin", "Cyberin"),
    ("hostingraja", "HostingRaja"),
    ("bigrock", "BigRock"),
    ("hosting_home", "Hosting Home"),
    ("vercel", "Vercel"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("hosting", "0007_project_upload_deployment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hostedproject",
            name="hosting_platform",
            field=models.CharField(choices=HOSTED_PROJECT_PLATFORMS, default="custom", max_length=32),
        ),
        migrations.AlterField(
            model_name="hostingprovider",
            name="provider",
            field=models.CharField(choices=PROVIDER_CHOICES, db_index=True, max_length=24),
        ),
        migrations.AlterField(
            model_name="hostinglink",
            name="provider",
            field=models.CharField(choices=PROVIDER_CHOICES, db_index=True, max_length=24),
        ),
    ]
