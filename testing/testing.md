```
docker-compose exec site python manage.py clear_submissions
docker-compose exec site python manage.py setup_test_users

python3 stress_test.py
```
