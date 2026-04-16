from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from project_review.models import Company

class Command(BaseCommand):
    help = 'Populates the database with sample company data.'

    def handle(self, *args, **options):
        self.stdout.write('Upserting companies (preserving existing logos if present)...')

        def slugify_name(name: str) -> str:
            return ''.join(c.lower() if c.isalnum() else '_' for c in name).strip('_')

        def company_initials(name: str) -> str:
            parts = [p for p in name.split() if p]
            if not parts:
                return 'C'
            if len(parts) == 1:
                return parts[0][0].upper()
            return (parts[0][0] + parts[-1][0]).upper()

        def placeholder_svg(name: str, bg_color: str = '#dc143c') -> bytes:
            initials = company_initials(name)
            svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' width='128' height='128'>
  <rect width='100%' height='100%' fill='{bg_color}' />
  <text x='50%' y='55%' dominant-baseline='middle' text-anchor='middle' font-family='Arial, sans-serif' font-size='56' fill='#ffffff'>{initials}</text>
</svg>
""".strip()
            return svg.encode('utf-8')

        self.stdout.write('Creating or updating: TCS, IBM, Zoho, Infosys, Cognizant, Amazon, HCL Technologies, Wipro, Capgemini, Tech Mahindra, DXC Technology...')
        companies_to_create = [
            {
                'name': 'TCS',
                'location': 'India',
                'phone': '+91 22 6778 9999',
                'rating': 4.8,
                'rating_count': 120,
                'price_range': '$$',
                'category': 'IT Services',
                'promoted': True,
            },
            {
                'name': 'IBM',
                'location': 'United States',
                'phone': '+1 800-426-4968',
                'rating': 4.2,
                'rating_count': 200,
                'price_range': '$$$',
                'category': 'Technology',
                'promoted': False,
            },
            {
                'name': 'Zoho',
                'location': 'India',
                'phone': '+91 44 7187 6500',
                'rating': 4.7,
                'rating_count': 150,
                'price_range': '$$',
                'category': 'SaaS',
                'promoted': True,
            },
            {
                'name': 'Infosys',
                'location': 'India',
                'phone': '+91 80 2852 0261',
                'rating': 4.0,
                'rating_count': 180,
                'price_range': '$$',
                'category': 'IT Services',
                'promoted': False,
            },
            {
                'name': 'Cognizant',
                'location': 'United States',
                'phone': '+1 201-801-0233',
                'rating': 3.8,
                'rating_count': 160,
                'price_range': '$$',
                'category': 'Consulting & IT',
                'promoted': False,
            },
            {
                'name': 'Amazon',
                'location': 'United States',
                'phone': '+1 888-280-4331',
                'rating': 3.9,
                'rating_count': 500,
                'price_range': '$$$',
                'category': 'Cloud & E-commerce',
                'promoted': True,
            },
            {
                'name': 'HCL Technologies',
                'location': 'India',
                'phone': '+91 120 480 1600',
                'rating': 4.3,
                'rating_count': 140,
                'price_range': '$$',
                'category': 'IT Services',
                'promoted': False,
            },
            {
                'name': 'Wipro',
                'location': 'India',
                'phone': '+91 80 2844 0011',
                'rating': 2.9,
                'rating_count': 170,
                'price_range': '$$',
                'category': 'IT Services',
                'promoted': False,
            },
            {
                'name': 'Capgemini',
                'location': 'France',
                'phone': '+33 1 47 54 50 00',
                'rating': 3.3,
                'rating_count': 160,
                'price_range': '$$',
                'category': 'Consulting & Technology',
                'promoted': False,
            },
            {
                'name': 'Tech Mahindra',
                'location': 'India',
                'phone': '+91 20 6601 8100',
                'rating': 4.3,
                'rating_count': 130,
                'price_range': '$$',
                'category': 'IT Services',
                'promoted': False,
            },
            {
                'name': 'DXC Technology',
                'location': 'United States',
                'phone': '+1 855-778-9183',
                'rating': 3.2,
                'rating_count': 120,
                'price_range': '$$',
                'category': 'IT Services',
                'promoted': False,
            },
        ]

        created_count = 0
        updated_count = 0

        for company_data in companies_to_create:
            name = company_data['name']
            defaults = {k: v for k, v in company_data.items() if k != 'name'}
            company, created = Company.objects.update_or_create(
                name=name,
                defaults=defaults,
            )

            if created:
                created_count += 1
                if not company.logo:
                    logo_bytes = placeholder_svg(name)
                    filename = f"company_logos/{slugify_name(name)}.svg"
                    company.logo.save(filename, ContentFile(logo_bytes), save=True)
            else:
                updated_count += 1
                # If logo missing on existing record, assign a placeholder to avoid broken images
                if not company.logo:
                    logo_bytes = placeholder_svg(name)
                    filename = f"company_logos/{slugify_name(name)}.svg"
                    company.logo.save(filename, ContentFile(logo_bytes), save=True)

        self.stdout.write(self.style.SUCCESS(f'Success: created {created_count}, updated {updated_count}.'))