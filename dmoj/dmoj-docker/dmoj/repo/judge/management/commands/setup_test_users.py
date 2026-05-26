from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from judge.models import Profile

NUMBER_OF_USERS = 10

class Command(BaseCommand):
    help = 'Creater N test users'

    def handle(self, *args, **kwargs):
        prefix = 'student_'
        count = NUMBER_OF_USERS
        password = 'testpassword123'

        self.stdout.write(self.style.WARNING(f"Deletes old data {prefix}* ..."))
        
        old_users = User.objects.filter(username__startswith=prefix)
        deleted_count, _ = old_users.delete()
        self.stdout.write(f"Deleted old accounts: {deleted_count}")

        self.stdout.write("Generating new accounts...")
        
        created_count = 0
        for i in range(1, count + 1):
            username = f"{prefix}{i}"
            
            user = User.objects.create_user(
                username=username,
                email=f"{username}@stress.test",
                password=password
            )
            
            Profile.objects.get_or_create(user=user)
            created_count += 1
            
        self.stdout.write(self.style.SUCCESS(
            f"Successfully creater {created_count} users.\n"
            f"Logins: from {prefix}1 to {prefix}{count}\n"
            f"Common password: {password}"
        ))