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

import os
import re
import random
import string
from stat import S_IRGRP
from datetime import datetime
from ConfigParser import ConfigParser

from django.conf import settings
from django.template.loader import render_to_string

class Tools():

    def handle_uploaded_file(self, f):

        uploadPath = settings.MEDIA_ROOT

        # create unique file name
        fileName = 'urls_' + self.randomize() + '.txt'
        while os.path.exists( os.path.join( uploadPath, fileName ) ):
            fileName = 'urls_' + self.randomize() + '.txt'

        filePath = os.path.join( uploadPath, fileName )

        # write file
        destination = open( filePath, 'wb+' )
        for chunk in f.chunks():
            destination.write(chunk)
        destination.close()

        # set read permission to group
        os.chmod(filePath, 0640)

        return fileName

    def randomize(self, size=8, chars=string.ascii_letters + string.digits):
         return ''.join( random.choice( chars ) for x in range( size ) )


class AnalyzerData(object):

    html = ""
    node = None

    def __processData(self, name, structure, value):

        if structure == 'list':

            if not value:
                self.html += render_to_string('analyzer_data.html', {'list_no_value': True, 'name': name})
            else:
                self.html += render_to_string('analyzer_data.html', {'list_w_value': True, 'name': name})

            for item in value:
                self.html += '<li>'
                self.__processData( item['name'], item['structure'], item['value'])
                self.html += '</li>'

            self.html += '</ul>'

        elif structure == 'text':
            if len(value) > 130:
                self.html += render_to_string('analyzer_data.html', {'text_gt_130': True, 'name': name, 'value': value})
            else:
                self.html += render_to_string('analyzer_data.html', {'text_lt_130': True, 'name': name, 'value': value})

        elif structure == 'boolean':
            self.html += render_to_string('analyzer_data.html', {'boolean': True, 'name': name, 'value': value})
        elif structure == 'integer':
            self.html += render_to_string('analyzer_data.html', {'integer': True, 'name': name, 'value': value})
        elif structure == 'time':
            try:
                dateValue = datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                dateValue = 'Cannot read timestamp.'
            self.html += render_to_string('analyzer_data.html', {'time': True, 'name': name, 'value': dateValue})
        elif structure == 'attachment':
            if self.node:
                self.html += render_to_string('analyzer_data.html', {'attachment_w_node': True, 'name': name, 'value': value, 'node': self.node})
            else:
                self.html += render_to_string('analyzer_data.html', {'attachment_no_node': True, 'name': name, 'value': value})

    def toHTML(self, analyzerData):
        self.html = '<div class="analyzerDataDiv">'
        if analyzerData:
            self.__processData( analyzerData['name'], analyzerData['structure'], analyzerData['value'] )
        else:
            self.html += 'Analyzer did not produce any analysis data.'
        self.html += '</div>'
        return self.html

    def setNode(self, node):
        self.node = node
