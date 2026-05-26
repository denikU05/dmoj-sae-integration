from django.core.management.base import BaseCommand
from judge.models import Submission

class Command(BaseCommand):
    help = 'Deletes all submissions'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Starting..."))
        
        # Получаем все объекты Submission в базе
        submissions = Submission.objects.all()
        total_count = submissions.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("Database is empty already."))
            return
            
        deleted_count, _ = submissions.delete()
        
        self.stdout.write(self.style.SUCCESS(
            f"Successfully deleted {total_count} subbmissions."
        ))