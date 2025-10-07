from django.core.management.base import BaseCommand
from django.utils import timezone
import random
import uuid

from chatcore.models import Source, ExternalContact, Conversation, Message

SAMPLE_TEXTS = [
    'Hello!',
    'Can you help me with my order?',
    'Thanks — that fixed it.',
    "I'm having trouble logging in.",
    'When will my shipment arrive?',
    'Any updates on this?',
    'Good morning!',
    'Please call me back.',
    'Is this available in other colors?',
    'I want to cancel my subscription.'
]


class Command(BaseCommand):
    help = 'Generate sample conversations and messages for development'

    def add_arguments(self, parser):
        parser.add_argument('--conversations', type=int, default=10, help='Number of conversations to create')
        parser.add_argument('--messages', type=int, default=5, help='Messages per conversation')
        parser.add_argument('--source-slug', type=str, default='local-mock', help='Source slug to attach conversations to')

    def handle(self, *args, **options):
        n_convs = options['conversations']
        n_msgs = options['messages']
        source_slug = options['source_slug']

        source, _ = Source.objects.get_or_create(slug=source_slug, defaults={'display_name': 'Local Mock Source', 'is_active': True})

        created_convs = 0
        created_msgs = 0

        for i in range(n_convs):
            ext_id = str(uuid.uuid4())[:8]
            contact = ExternalContact.objects.create(source=source, external_id=f'user-{ext_id}', display_name=f'User {ext_id}')
            conv = Conversation.objects.create(source=source, external_contact=contact, title=f'Conv {ext_id}')
            created_convs += 1

            for j in range(n_msgs):
                # random direction
                direction = random.choice([Message.DIRECTION_IN, Message.DIRECTION_OUT])
                text = random.choice(SAMPLE_TEXTS)
                msg = Message.objects.create(
                    conversation=conv,
                    direction=direction,
                    sender_name=(contact.display_name if direction == Message.DIRECTION_IN else 'Admin'),
                    content=text,
                    external_message_id=(str(uuid.uuid4()) if direction == Message.DIRECTION_IN else None),
                    source=source,
                    status=(Message.STATUS_RECEIVED if direction == Message.DIRECTION_IN else Message.STATUS_SENT),
                )
                created_msgs += 1

        self.stdout.write(self.style.SUCCESS(f'Created {created_convs} conversations and {created_msgs} messages (source={source_slug})'))
