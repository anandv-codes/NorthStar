import sys
sys.path.insert(0, '/var/task')

from app.workers.note_processor import lambda_handler

# Lambda expects this handler function
__all__ = ['lambda_handler']
