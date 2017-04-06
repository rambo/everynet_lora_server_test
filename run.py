#!/usr/bin/env python
import logging
from logging.handlers import RotatingFileHandler
from app import app
handler = RotatingFileHandler('foo.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.run(debug=True, port=8000)
