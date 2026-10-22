"""
passenger_wsgi.py - Phusion Passenger entrypoint for cPanel / CloudLinux.
Directs incoming web requests to the Tancoin Django WSGI application.
"""

import os
import sys

# Ensure current project directory is in Python's search path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tancoin.settings")

# Expose WSGI callable for Passenger
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
