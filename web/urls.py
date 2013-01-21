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
#from django.conf.urls import patterns, include, url #Django 1.4
from django.conf.urls.defaults import patterns, include, url

from django.contrib import admin
from django.contrib.sites.models import Site
from django.contrib.auth.models import Group

from web.app.feeds import AllUrls, NonBenignUrls

static_admin = os.path.join(os.path.dirname(__file__), 'app/static_admin')

admin.autodiscover()

urlpatterns = patterns('web.app.views',

    (r'^$', 'jobs_overview'),
    (r'^jobs/$', 'jobs_overview'),

    (r'^job/(?P<job_id>\d+)/$', 'job_details'),

    (r'^job/(?P<job_id>\d+)/analysis/(?P<node>\d+:\d+)/$', 'analysis_overview'),
    (r'^job/(?P<job_id>\d+)/analysis/(?P<node>\d+:\d+)/byanalyzer/(?P<analyzer>[\w-]+)/$', 'analysis_by_analyzer'),
    (r'^job/(?P<job_id>\d+)/analysis/(?P<node>\d+:\d+)/byurl/(?P<subnode>\d+:\d+)/$', 'analysis_by_url'),

    (r'^getattachment/(?P<node>\d+:\d+:?\w*)/(?P<filename>\d+:\d+:\d+)/$', 'get_attachment'),

    (r'^schedule/$', 'schedule_overview'),
    (r'^schedule/(?P<job_id>\d+)/$', 'schedule_details'),
    (r'^schedule/edit/(?P<job_id>\d+)/$', 'schedule_details_edit'),
    (r'^schedule/lastrun/(?P<job_id>\d+)/$', 'schedule_lastrun'),

    (r'^newjob/$', 'new_job'),
    (r'^newjobdone/(?P<job_id>\d+)/$', 'new_job_done'),

    (r'^nopermission/$', 'no_permission'),
    (r'^about/$', 'about_page'),
    (r'^logout/$', 'logout_page'),
    (r'^switchuser/$', 'switch_user'),

    (r'^statistics/$', 'statistics_page'),

    # AJAX REQUESTS
    (r'^getanalyzerdetails/$', 'get_analyzer_details'),
    (r'^schedule/disable/$', 'disable_schedule'),
    (r'^schedule/delete/$', 'delete_schedule'),
    (r'^getworkflowdetails/$', 'get_workflow_details')

)

#TODO: login with REMOTE_USER for SSO
urlpatterns += patterns('',
    (r'^login/$', 'django.contrib.auth.views.login', {'template_name': 'login.html'}),
    (r'^static_admin/(?P<path>.*)$', 'django.views.static.serve', { 'document_root': static_admin }),
    (r'^password/$', 'django.contrib.auth.views.password_change', {'template_name': 'registration/password_change_form.html'} ),
    (r'^password_done/$', 'django.contrib.auth.views.password_change_done' ),

    (r'^feeds/(?P<job_id>\d+)/all/$', AllUrls() ),
    (r'^feeds/(?P<job_id>\d+)/nonbenign/$', NonBenignUrls() ),

    (r'^admin/', include(admin.site.urls)),
)
