from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from chatcore.models import Conversation


class Command(BaseCommand):
    help = 'Add the admin user as participant to all conversations (for dev testing)'

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            admin = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR('Admin user not found'))
            return

        convs = Conversation.objects.all()
        count = 0
        for c in convs:
            c.participants.add(admin)
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Added admin to {count} conversations'))
