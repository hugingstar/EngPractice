import os
from django.db import connection
from django.http import JsonResponse
from django.conf import settings

def execute_sql_file(filename, params=None):
    filepath = os.path.join(settings.BASE_DIR, 'queries', filename)
    with open(filepath, 'r') as f:
        sql = f.read()
    with connection.cursor() as cursor:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        if sql.strip().upper().startswith("SELECT"):
            columns = [col[0] for col in cursor.description]
            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]
        return None

def setup_manager_log_table():
    execute_sql_file('001_create_manager_log.sql')

def log_event(event_type, description):
    with connection.cursor() as cursor:
        cursor.execute("INSERT INTO manager_log (event_type, description) VALUES (%s, %s)", [event_type, description])

def get_recent_logs(request):
    try:
        setup_manager_log_table()
        logs = execute_sql_file('002_select_recent_logs.sql')
        return JsonResponse({"logs": logs})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
