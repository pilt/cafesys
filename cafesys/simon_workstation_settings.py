# -*- coding: utf-8 -*-

DEBUG = True
LDAP_ENABLED = False
STATS_CACHE = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2", # Add "postgresql_psycopg2", "postgresql", "mysql", "sqlite3" or "oracle".
        "NAME": "cafesys",                       # Or path to database file if using sqlite3.
        "TEST_NAME": "test_cafesys",
        "USER": "sp",                             # Not used with sqlite3.
        "PASSWORD": "",                         # Not used with sqlite3.
        "HOST": "",                             # Set to empty string for localhost. Not used with sqlite3.
        "PORT": "",                             # Set to empty string for default. Not used with sqlite3.
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
#EMAIL_HOST = 'smtp.bahnhof.se'
EMAIL_HOST = ''
EMAIL_PORT = 25
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = 'noreply@ejlert.spantz.org'

SITE_ID=2

# For importing data from the old system. There is a management command
# that uses these settings (importoldsystem).
OLD_SYSTEM_MYSQL_LOGIN = 'root'
OLD_SYSTEM_MYSQL_PASSWORD = 'w1zard'
OLD_SYSTEM_MYSQL_DB = 'baljan'
OLD_SYSTEM_MYSQL_HOST = 'localhost'

ANALYTICS_KEY= ''
