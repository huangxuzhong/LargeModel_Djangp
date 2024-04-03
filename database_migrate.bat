@echo off  
python manage.py makemigrations  
python manage.py migrate  
echo Migrations completed.  
pause