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
import re
from django.conf import settings
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.utils.datastructures import SortedDict
from couchdb.client import Server
from datetime import datetime, timedelta
from web.app.models import *


class JobFeed(Feed):

    def get_object(self, request, job_id):
        return get_object_or_404(Schedule, id=job_id)

    def description(self, scheduledJob):
        if scheduledJob.scheduled_start is not None:
            return "Job is scheduled to run on %s" % ( scheduledJob.scheduled_start )
        else:
            return "Job is scheduled to with cron expression %s" % ( scheduledJob.cron_expression )

    def item_title(self, item):
        itemTitle = "[%s] %s" % (item['classification'], item['url'])
        return itemTitle

    def item_description(self, item):
        description = "Processed on %s.<br>%s is classified as %s.<br>Processed %s subpages." % \
            (item['started'], item['url'], item['classification'], item['pageCount'])
        return description

    def item_link(self, item):
        link = "/job/%s/analysis/%s/" % ( item['jobId'], item['node'])
        return link

    def items(self, scheduledJob):
        # select couchdb
        try:
            couch = Server(settings.COUCHDB_SERVER)
            db = couch[settings.COUCHDB_NAME]
        except:
            pass

        urls = {}
        
        daysAgo = settings.FEEDS_HISTORY_DAYS if re.match(r'^\d+$', '%s' % settings.FEEDS_HISTORY_DAYS) else 7

        for job in Job.objects.filter(schedule=scheduledJob, started__gte = datetime.now() - timedelta(days=daysAgo)):
            if job.frameworkid:
                jobFrameworkId = job.frameworkid
                sortingKeyDate = job.started.strftime('%Y%m%d%H%M%S')

                for url in db.view('url_by_fwid/view', key=jobFrameworkId):
                    topAncestor = url.value['top_ancestor']
                    classification = url.value['classification'].upper()

                    nodeId = '%s:%s' % (jobFrameworkId, topAncestor)
                    sortingKey = '%s_%s' % (sortingKeyDate, nodeId)

                    if sortingKey in urls:
                        urls[sortingKey]['pageCount'] += 1

                        # set the top ancestor url
                        if nodeId == url.id:
                            urls[sortingKey]['url'] = url.value['url']
                            urls[sortingKey]['node'] = url.id

                        # set the overall classification for the url
                        if CLASSIFICATIONS[classification] > CLASSIFICATIONS[urls[sortingKey]['classification']]:
                            urls[sortingKey]['classification'] = classification

                    else:
                        urls[sortingKey] = {'classification': classification, \
                                        'url': url.value['url'], \
                                        'node': url.id, \
                                        'pageCount': 1, \
                                        'jobId': job.id, \
                                        'started': job.started}
        
        sortedUrls = SortedDict()
        for key in sorted(urls.iterkeys(), reverse=True):
            sortedUrls[key] = urls[key]

        return sortedUrls.values()
    


class AllUrls(JobFeed):
    def title(self, scheduledJob):
        return "All URLs for '%s'" % scheduledJob.job_name

    def link(self, scheduledJob):
        return '/feeds/%s/all/' % scheduledJob.id


class NonBenignUrls(JobFeed):
    def title(self, scheduledJob):
        return "Non-Benign URLs for '%s'" % scheduledJob.job_name

    def link(self, scheduledJob):
        return '/feeds/%s/all/' % scheduledJob.id

    def items(self, scheduledJob):

        urls = super(NonBenignUrls, self).items(scheduledJob)

        urlsList = []
        for details in urls:
            if details['classification'] != 'BENIGN':
                urlsList.append(details)

        return urlsList
