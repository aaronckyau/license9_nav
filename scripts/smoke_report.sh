#!/bin/sh
set -eu

python manage.py generate_sample_report
python manage.py shell -c "from navapp.models import GeneratedFile; assert GeneratedFile.objects.filter(file_type='DOCX', size__gt=0).exists(); assert GeneratedFile.objects.filter(file_type='PDF', size__gt=0).exists(); print('DOCX/PDF smoke test passed')"
