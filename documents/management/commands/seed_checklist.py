from django.core.management.base import BaseCommand

from documents.models import DocumentType

CHECKLIST = [
    ('Passport bio page', 'Photo page showing your passport number, issuing country, and expiry date.'),
    ('Proof of enrollment', 'A signed letter or certificate from your institution confirming current enrollment.'),
    ('Visa or residence permit', 'A copy of your current student visa or residence permit.'),
    ('Official university document showing nationality', 'A university-issued document confirming your nationality on record.'),
]


class Command(BaseCommand):
    help = 'Creates the standard international-student document checklist.'

    def handle(self, *args, **options):
        created = 0
        for order, (name, description) in enumerate(CHECKLIST, start=1):
            _, was_created = DocumentType.objects.update_or_create(
                name=name,
                defaults={'description': description, 'order': order, 'is_required': True},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f'Checklist ready — {created} new item(s), {len(CHECKLIST)} total.'))