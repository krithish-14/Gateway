import os
import django
from django.db import connection

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'final_setup.settings')
django.setup()

def check_sql_mail_status():
    print("Checking MS SQL Database Mail status...")
    
    try:
        with connection.cursor() as cursor:
            # 1. Check if Database Mail is enabled
            cursor.execute("EXEC sp_configure 'Database Mail XPs'")
            row = cursor.fetchone()
            if row:
                config_value = row[3] # run_value is usually the 4th column
                print(f"Database Mail XPs run_value: {config_value}")
            
            # 2. Check recent mail items
            print("\nRecent Mail Items (Last 5):")
            cursor.execute("SELECT TOP 5 * FROM msdb.dbo.sysmail_allitems ORDER BY sent_date DESC")
            columns = [column[0] for column in cursor.description]
            print(f"Columns in sysmail_allitems: {columns}")
            items = cursor.fetchall()
            if not items:
                print("No mail items found in msdb.dbo.sysmail_allitems.")
            for item in items:
                print(f"ID: {item[0]} | To: {item[1]} | Subj: {item[2]} | Status: {item[3]} | Date: {item[4]}")

            # 3. Check for errors in the log
            print("\nRecent Mail Errors (Last 5):")
            cursor.execute("""
                SELECT TOP 5 log_id, event_type, log_date, description 
                FROM msdb.dbo.sysmail_event_log 
                WHERE event_type != 'Information'
                ORDER BY log_date DESC
            """)
            errors = cursor.fetchall()
            if not errors:
                print("No recent errors found in msdb.dbo.sysmail_event_log.")
            for err in errors:
                print(f"LogID: {err[0]} | Type: {err[1]} | Date: {err[2]} | Desc: {err[3]}")

    except Exception as e:
        print(f"Error checking status: {e}")

if __name__ == "__main__":
    check_sql_mail_status()
