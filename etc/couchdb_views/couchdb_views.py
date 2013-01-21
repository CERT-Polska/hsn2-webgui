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

import os
import sys
import urllib
from httplib import *

try:
    import simplejson as json
except ImportError:
    import json

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
os.environ["DJANGO_SETTINGS_MODULE"]="web.settings"
from django.conf import settings
from django.utils.http import urlencode


class CouchDBException(Exception):
    pass


class CouchDB(object):

    def __init__(self, host='http://127.0.0.1:5984', db='hsn'):
        # strip trailing forwardslash from host
        if host.endswith("/"):
            host = host[:-1]
        self.host = host
        self.db = db

## MAIN ACTIONS ##
    def syncViews(self):
        views = self.getLocalViews()

        currentPath = os.path.dirname(__file__) or "."

        res = None
        for design, viewList in views.iteritems():

            # check if design document exists with an HEAD request
            try:
                url = "/%s/_design/%s" % (self.db, design)
                conn = HTTPConnection(self.stripProtocolFromHost())
                conn.request("HEAD", url)
                res = conn.getresponse()
            except HTTPException as e:
                print e
            except Exception as e:
                print e

            # if design document exists (HTTP status 200)
            if res.status == 200:
                revFile = "%s/%s/rev" % (currentPath, design)
                query = "_design/%s" % design
                designDoc = self.query(query)

                # check if file with revision details exists
                if os.path.exists( revFile ):
                    revDetailsFile = None
                    try:
                        revDetailsFile = open(revFile, 'r').read()
                    except IOError as e:
                        print "Cannot open %s. Reason: %s" % ( revFile, e)
                        continue

                    revDetails = json.loads(revDetailsFile)
                    localHasChanged = False

                    # check for each view if the map.js or reduce.js file has changed
                    for view in viewList:
                        viewPath = "%s/%s/%s" % (currentPath, design, view)
                        for mapReduce in ['map', 'reduce']:

                            mapReduceFile = os.path.join(viewPath, '%s.js' % mapReduce)
                            if os.path.exists(mapReduceFile):
                                if revDetails.has_key(view) and revDetails[view].has_key(mapReduce):
                                    fileInfo = os.stat(mapReduceFile)
                                    if revDetails[view][mapReduce] != fileInfo.st_mtime:
                                        # content of map or reduce file has changed:
                                        localHasChanged = True
                                else:
                                    # map or reduce file is new
                                    localHasChanged = True
                            else:
                                if revDetails.has_key(view) and revDetails[view].has_key(mapReduce):
                                    # map or reduce file has been deleted
                                    localHasChanged = True

                    # check if views have been deleted locally
                    for view in revDetails.keys():
                        if view != 'rev' and view not in viewList:
                            localHasChanged = True

                    if designDoc.has_key('_rev') and designDoc['_rev'] == revDetails['rev'] and not localHasChanged:
                        print "_design/%s is up to date" % design
                        continue
                    else:
                        updateDesignDoc = self.setDesignDocument(design, viewList, doc=designDoc)
                        putResult = self.put(design, updateDesignDoc)

                else: # rev file doe not exist
                    updateDesignDoc = self.setDesignDocument(design, viewList, doc=designDoc)
                    putResult = self.put(design, updateDesignDoc)
            else: # design document does not exist
                newDesignDoc = self.setDesignDocument(design, viewList)
                putResult = self.put(design, newDesignDoc)

            if putResult.status == 201:
                query = "_design/%s" % design
                designDoc = self.query(query)
                revDetails = {'rev': designDoc['_rev']}

                for view in viewList:
                    revDetails[view] = {}
                    viewPath = "%s/%s/%s" % (currentPath, design, view)
                    for mapReduce in ['map', 'reduce']:
                        mapReduceFile = os.path.join(viewPath, '%s.js' % mapReduce)
                        if os.path.exists(mapReduceFile):
                            fileInfo = os.stat(mapReduceFile)
                            revDetails[view][mapReduce] = fileInfo.st_mtime

                revFile = None
                revFilePath = "%s/%s/rev" % (currentPath, design)
                try:
                    revFile = open(revFilePath, 'w+')
                    revFile.write(json.dumps(revDetails))
                    revFile.close()
                except IOError as e:
                    print "Cannot write to %s. Reason: %s" % ( revFile, e)
                    continue

                print "%s successfully synced" % design
            else:
                print "%s %s" % (putResult.status, putResult.reason)

    def listViews(self):
        query = '_all_docs?startkey="_design"&endkey="_design0"'
        designDocs = self.query(query)

        print "Views on server:"
        for row in designDocs['rows']:
            print row['id']
            viewDocs = self.query(row['id'])
            for view in  viewDocs['views']:
                print "\t" + view

        print "\nViews on local machine:"

        for design, viewList in self.getLocalViews().iteritems():
            print "_design/%s" % design
            for view in viewList:
                print "\t" + view

#TODO: delete all designs which are not present local
    def cleanUp(self):
        pass

## HELPERS ##
    def query(self, query):

        url = self.host + "/" + self.db + "/" + query
        try:
            url_json = urllib.urlopen(url).read()
            queryResult = json.loads(url_json)
        except IOError as e:
            raise  CouchDBException(e)
        except ValueError as e:
            raise CouchDBException(e)
        except Exception as e:
            raise CouchDBException("Unknown error: %s" % e)

        return queryResult

    def getLocalViews(self):
        iteration = 0
        designs = []
        views = {}

        walkFrom = os.path.dirname(__file__) or "."

        for dirname, dirnames, filenames in os.walk(walkFrom):
            if "/." in dirname:
                continue

            if dirnames:
                if len(dirnames) == 1 and dirnames[0].startswith("."):
                    del dirnames[0]
                    continue

                dirnames.sort()

                if iteration != 0:
                    views[designs[iteration-1]] = []

                for subdirname in dirnames:
                    if iteration == 0:
                        if not subdirname.startswith("."):
                            designs.append(subdirname)
                    else:
                        if not subdirname.startswith("."):
                            views[designs[iteration-1]].append(subdirname)
                iteration += 1

        return views

    def setDesignDocument(self, design, views, doc=None):
        designDoc = {'_id': design, 'language': 'javascript', 'views': {}} if not doc else doc

        currentPath = os.path.dirname(__file__) or "."

        # add or update view in designDoc
        for view in views:
            mapFile = "%s/%s/%s/map.js" % (currentPath, design, view)
            if os.path.exists(mapFile):
                try:
                    mapFunc = open(mapFile, 'r').read()
                except IOError as e:
                    print "Cannot open %s. Reason: %s" % ( mapFile, e)
                designDoc['views'][view] = {}
                designDoc['views'][view]['map'] = mapFunc

            reduceFile = "%s/%s/%s/reduce.js" % (currentPath, design, view)
            if os.path.exists(reduceFile):
                try:
                    reduceFunc = open(reduceFile, 'r').read()
                except IOError as e:
                    print "Cannot open %s. Reason: %s" % ( reduceFile, e)
                designDoc['views'][view]['reduce'] = reduceFunc

        # delete views from designDoc which don't exist locally
        for view in designDoc['views'].keys():
            if view not in views:
                del designDoc['views'][view]

        return json.dumps(designDoc)

    def put(self, design, designDoc):
        try:
            url = "/%s/_design/%s" % (self.db, design)
            conn = HTTPConnection(self.stripProtocolFromHost())
            conn.request("PUT", url, designDoc)
            return conn.getresponse()
        except HTTPException as e:
            print e
        except Exception as e:
            print e

    def stripProtocolFromHost(self):
        host = self.host
        if host.startswith('http://'):
            host = host[7:]
        if host.startswith('https://'):
            host = host[8:]
        return host


if __name__ == "__main__":

    couch = CouchDB(host=settings.COUCHDB_SERVER, db=settings.COUCHDB_NAME)

    if len(sys.argv) == 2:
        if sys.argv[1] == '--list' or sys.argv[1] == '-l':
            try:
                couch.listViews()
            except CouchDBException as e:
                print e
        elif sys.argv[1] == '--sync' or sys.argv[1] == '-s':
            couch.syncViews()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print """
Usage: %s OPTION
    -l, --list    list views
    -s, --sync    sync views
""" % sys.argv[0]

        sys.exit(2)
