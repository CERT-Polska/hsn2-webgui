#!/usr/bin/env python

# Copyright (c) NASK, NCSC
# 
# This file is part of HoneySpider Network 2.0.
# 
# This is a free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from couchdb import *
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
os.environ["DJANGO_SETTINGS_MODULE"]="web.settings"
from django.conf import settings

host = settings.COUCHDB_SERVER
dbName = settings.COUCHDB_NAME
try:
    server = Server(host)
    db = server[dbName]
except:
    print "Cannot establish a connection with couchdb."
else:
    for row in db.view('analysis/all_analysis', None, include_docs=True ):
        db.delete( row.doc )
        
    for row in db.view('url_all_urls/view', None, include_docs=True, reduce='false' ):
        db.delete( row.doc )

    for row in db.view('file_all_files/view', None, include_docs=True, reduce='false' ):
        db.delete( row.doc )

    db.compact()