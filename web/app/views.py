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

try:
    import simplejson as json
except ImportError:
    import json

import urllib
from datetime import datetime, timedelta
import calendar
from ConfigParser import ConfigParser

from couchdb.client import Server

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.auth.views import login
from django import http, forms
from django.http import HttpResponse, HttpResponseRedirect, Http404, HttpResponseServerError
from django.shortcuts import get_object_or_404
from django.utils.encoding import smart_str

from web.app.models import *
from web.app.tools import *
from web.app.forms import *
from web.app.custom.shortcuts import render_response

### FOR DEVELOPMENT ONLY ###
#import logging.config
#from logging import getLogger
#
#logging.config.fileConfig('/srv/www/hsn2/web/logging.conf')
#log = logging.getLogger('framework')
############################
#TODO: admin en changepassword --> switch user bij SSO

@login_required
def new_job(request):
    configParser = ConfigParser()
    tools = Tools()

    parameterGroupNumbers = []
    # new job form has been submitted
    if request.method == u'POST':

        # add dynamic fields to form so they can be validaded like other fields
        parameterFields = {}
        for inputFieldName, inputFieldValue in request.POST.iteritems():
            if inputFieldName.startswith('workflow_parameter'):
                parameterFields[inputFieldName] = forms.CharField( required=False, widget=forms.TextInput( attrs={'class': 'minwidth_200'}) )
            if inputFieldName.startswith('workflow_parameter_service'):
                parameterGroupNumbers.append( re.sub(r'.*?_(\d+)$', r'\1', inputFieldName) )

        ExtendedJobForm = type("ExtendedJobForm", (JobForm,), parameterFields)
        newJobForm = ExtendedJobForm(request.POST)

        # if form is valid, save all formdata to database
        if newJobForm.is_valid():

            newSchedule = Schedule()

            newSchedule.created_by = request.user
            newSchedule.workflow = newJobForm.cleaned_data['workflow']
            newSchedule.is_public = newJobForm.cleaned_data['is_public']
            newSchedule.job_name = newJobForm.cleaned_data['job_name']

            if newJobForm.cleaned_data['schedule_when'] == 'now':
                newSchedule.frequency = Schedule.ONCE_FREQUENCY
            else:
                newSchedule.frequency = newJobForm.cleaned_data['schedule_frequency']
                scheduleDate = newJobForm.cleaned_data['schedule_date']
                scheduleTime = newJobForm.cleaned_data['schedule_time']
                newSchedule.scheduled_start = datetime( scheduleDate.year, scheduleDate.month, scheduleDate.day, scheduleTime.hour, scheduleTime.minute )

            newSchedule.save()

            if newJobForm.cleaned_data.has_key('feeder_file') and request.FILES:

                feederParameter = ServiceParameter()

                feederParameter.service = settings.FILE_FEEDER_ID 
                feederParameter.param_key = settings.FILE_FEEDER_PARAMETER_NAME

                # process uploaded file
                if request.FILES:
                    uploadedFileName = tools.handle_uploaded_file( request.FILES['feeder_file'] )
                    feederParameter.param_value = uploadedFileName

                    feederParameter.schedule = newSchedule
                    feederParameter.save()

            # add parameters
            for parameterGroupNumber in parameterGroupNumbers:
                if newJobForm.cleaned_data['workflow_parameter_service_%s' % parameterGroupNumber] \
                    and newJobForm.cleaned_data['workflow_parameter_name_%s' % parameterGroupNumber] \
                    and newJobForm.cleaned_data['workflow_parameter_value_%s' % parameterGroupNumber]:

                    newParameter = ServiceParameter( 
                                                    service=newJobForm.cleaned_data['workflow_parameter_service_%s' % parameterGroupNumber],
                                                    param_key=newJobForm.cleaned_data['workflow_parameter_name_%s' % parameterGroupNumber],
                                                    param_value=newJobForm.cleaned_data['workflow_parameter_value_%s' % parameterGroupNumber],
                                                    schedule=newSchedule
                                                    )
                    newParameter.clean()
                    newParameter.save()

            return HttpResponseRedirect('/newjobdone/%s/' % newSchedule.id)

    else:
        newJobForm = JobForm()

    return render_response(request, 'new_job.html',
                          {'createjob_selected': True,
                           'jobForm': newJobForm,
                           'parameterGroupNumbers': sorted(parameterGroupNumbers),
                           'parameterPrefixes': ['workflow_parameter_service_', 'workflow_parameter_name_', 'workflow_parameter_value_']
                           })

@login_required
def new_job_done(request, job_id):
    scheduledJob = get_object_or_404(Schedule, id=job_id)
    return render_response(request, 'new_job_done.html', {'createjob_selected': True, 'scheduledJob': scheduledJob})

@login_required
def schedule_overview(request):
    all_schedules = Schedule.objects.filter(is_deleted=False).order_by('-last_submit')

    paginator = Paginator(all_schedules, 30)

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    try:
        schedule = paginator.page(page)
    except (EmptyPage, InvalidPage):
        schedule = paginator.page(paginator.num_pages)

    return render_response(request, 'schedule_overview.html', {'schedule_selected': True, 'schedule':schedule})

@login_required
def schedule_details(request, job_id):

    scheduledJob = get_object_or_404(Schedule, id=job_id, is_deleted=False)

    jobs = Job.objects.filter(schedule=scheduledJob).order_by('-started')

    user = request.user
    if not user.is_superuser and scheduledJob.created_by is not user and not scheduledJob.is_public:
        return HttpResponseRedirect('/nopermission/')    

    return render_response(request, 'schedule_details.html', \
                          {'schedule_selected': True, \
                           'scheduledJob': scheduledJob, \
                           'jobs': jobs})

@login_required
def schedule_details_edit(request, job_id):
    scheduledJob = get_object_or_404(Schedule, id=job_id, is_deleted=False)

    user = request.user
    if not user.is_superuser and scheduledJob.created_by is not user:
        return HttpResponseRedirect('/nopermission/')

    tools = Tools()

    formInput = {}
    parameterFields = {}
    parameterGroupNumbers = []
    feederFileIsUsed = False

    # schedule details have been edited
    if request.method == u'POST':

        parameterFields = {}
        for inputFieldName, inputFieldValue in request.POST.iteritems():
            if inputFieldName.startswith('workflow_parameter'):
                parameterFields[inputFieldName] = forms.CharField( required=False, widget=forms.TextInput( attrs={'class': 'minwidth_200'}) )
            if inputFieldName.startswith('workflow_parameter_service'):
                parameterGroupNumbers.append( re.sub(r'.*?_(\d+)$', r'\1', inputFieldName) )

        ExtendedJobForm = type("ExtendedJobForm", (JobForm,), parameterFields)
        jobForm = ExtendedJobForm(request.POST)

        if jobForm.is_valid():

            scheduledJob.workflow = jobForm.cleaned_data['workflow']
            scheduledJob.is_public = True if jobForm.cleaned_data['is_public'] == "1" \
                else False
            scheduledJob.job_name = jobForm.cleaned_data['job_name']

            if jobForm.cleaned_data['schedule_when'] == 'now':
                scheduledJob.frequency = Schedule.ONCE_FREQUENCY
                scheduledJob.scheduled_start = None
            else:
                scheduledJob.frequency = jobForm.cleaned_data['schedule_frequency']
                scheduleDate = jobForm.cleaned_data['schedule_date']
                scheduleTime = jobForm.cleaned_data['schedule_time']
                scheduledJob.scheduled_start = datetime( scheduleDate.year, scheduleDate.month, scheduleDate.day, scheduleTime.hour, scheduleTime.minute )

            # add posted parameters
            postedParameters = []
            for parameterGroupNumber in parameterGroupNumbers:
                if jobForm.cleaned_data['workflow_parameter_service_%s' % parameterGroupNumber] \
                    and jobForm.cleaned_data['workflow_parameter_name_%s' % parameterGroupNumber] \
                    and jobForm.cleaned_data['workflow_parameter_value_%s' % parameterGroupNumber]:

                    parameterService = jobForm.cleaned_data['workflow_parameter_service_%s' % parameterGroupNumber]
                    parameterName = jobForm.cleaned_data['workflow_parameter_name_%s' % parameterGroupNumber]
                    parameterValue = jobForm.cleaned_data['workflow_parameter_value_%s' % parameterGroupNumber]

                    parameter, created = ServiceParameter.objects.get_or_create( schedule=scheduledJob, service=parameterService, param_key=parameterName )
                    parameter.param_value = parameterValue
                    parameter.clean()
                    parameter.save()
                    postedParameters.append('%s%s' % (parameterService, parameterName))

            if jobForm.cleaned_data.has_key('feeder_file') and request.FILES:
                # process uploaded file
                feederParameter, created = ServiceParameter.objects.get_or_create( schedule=scheduledJob, service=settings.FILE_FEEDER_ID, param_key=settings.FILE_FEEDER_PARAMETER_NAME )
                uploadedFileName = tools.handle_uploaded_file(request.FILES['feeder_file'])

                feederParameter.param_value = uploadedFileName
                feederParameter.save()
                postedParameters.append('%s%s' % (settings.FILE_FEEDER_ID, settings.FILE_FEEDER_PARAMETER_NAME))

            if request.POST.has_key('feederFileIsUsed') and request.POST['feederFileIsUsed'] == 'True':
                postedParameters.append('%s%s' % (settings.FILE_FEEDER_ID, settings.FILE_FEEDER_PARAMETER_NAME))

            # clean up unused parameters for this schedule 
            for parameter in scheduledJob.parameters.all():
                parameterCheck = '%s%s' % (parameter.service, parameter.param_key)
                if parameterCheck not in postedParameters:
                    parameter.delete()

            scheduledJob.save()

            # change the is_public setting for processed jobs
            if jobForm.cleaned_data['edit_processed_jobs'] == "1" \
                and jobForm.cleaned_data['is_public'] != jobForm.cleaned_data['is_public_org']:
                Job.objects.select_related().filter(schedule=scheduledJob).update(is_public=scheduledJob.is_public)

            return HttpResponseRedirect("/schedule/%s/" % scheduledJob.id)

    # show the schedule edit form
    else:
        parameterCount = 1
        for parameter in scheduledJob.parameters.all():
            if parameter.service == settings.FILE_FEEDER_ID:
                feederFileIsUsed = True
                formInput['feeder_file'] = parameter.param_value
                continue

            formInput['workflow_parameter_service_%s' % parameterCount] = parameter.service
            formInput['workflow_parameter_name_%s' % parameterCount] = parameter.param_key
            formInput['workflow_parameter_value_%s' % parameterCount] = parameter.param_value

            parameterFields['workflow_parameter_service_%s' % parameterCount] = forms.CharField( required=False, widget=forms.TextInput( attrs={'class': 'minwidth_200'}) )
            parameterFields['workflow_parameter_name_%s' % parameterCount] = forms.CharField( required=False, widget=forms.TextInput( attrs={'class': 'minwidth_200'}) )
            parameterFields['workflow_parameter_value_%s' % parameterCount] = forms.CharField( required=False, widget=forms.TextInput( attrs={'class': 'minwidth_200'}) )
            parameterGroupNumbers.append( str(parameterCount) )
            parameterCount += 1

        if scheduledJob.frequency == Schedule.ONCE_FREQUENCY and scheduledJob.scheduled_start is None:
            formInput['schedule_when'] = 'now'
        else:
            formInput['schedule_when'] = 'later'

        formInput['schedule_date'] = scheduledJob.scheduled_start
        formInput['schedule_time'] = scheduledJob.scheduled_start
        formInput['schedule_frequency'] = scheduledJob.frequency
        formInput['is_public'] = 1 if scheduledJob.is_public else 0
        formInput['job_name'] = scheduledJob.job_name
        formInput['workflow'] = scheduledJob.workflow.id
        formInput['workflow_xml'] = scheduledJob.workflow.xml
        formInput['workflow_description'] = scheduledJob.workflow.description

        ExtendedJobForm = type("ExtendedJobForm", (JobForm,), parameterFields)
        jobForm = ExtendedJobForm(formInput)

    return render_response(request, 'schedule_details_edit.html', \
                          {'schedule_selected': True, \
                           'scheduledJob': scheduledJob, \
                           'jobForm': jobForm,
                           'parameterGroupNumbers': parameterGroupNumbers,
                           'parameterPrefixes': ['workflow_parameter_service_', 'workflow_parameter_name_', 'workflow_parameter_value_'],
                           'feederFileIsUsed': feederFileIsUsed
                           })

@login_required
def schedule_lastrun(request, job_id):
    jobSchedule = get_object_or_404(Schedule, id=job_id)

    if jobSchedule.last_submit:
        job = get_object_or_404(Job, schedule=jobSchedule, started=jobSchedule.last_submit)
        return HttpResponseRedirect("/job/%s/" % job.id)
    else:
        raise Http404

@login_required
def jobs_overview(request):
    all_jobs = Job.objects.all().order_by('-started')
    paginator = Paginator(all_jobs, 30)

    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1

    try:
        jobs = paginator.page(page)
    except (EmptyPage, InvalidPage):
        jobs = paginator.page(paginator.num_pages)
    return render_response(request, 'jobs_overview.html', {'jobs_selected': True, 'jobs': jobs})

@login_required
def job_details(request, job_id):
    job = get_object_or_404(Job, id=job_id)

    # check user permission for page
    user = request.user
    if not user.is_superuser and job.owner is not user and not job.is_public:
        return HttpResponseRedirect('/nopermission/')

    tools = Tools()

    queryResultMessage = ""

    # select couchdb
    try:
        couch = Server(settings.COUCHDB_SERVER)
        db = couch[settings.COUCHDB_NAME]
    except Exception as e:
        queryResultMessage = str(e) + ". "

    jobFrameworkId = "%s" % job.frameworkid
    urls = {}
    urlClassification = {}

    # query couchdb
    try:
        for url in db.view('url_by_fwid/view', key=jobFrameworkId):
            topAncestor = url.value['top_ancestor']
            classification = url.value['classification'].upper()

            if topAncestor in urls:
                nodeId = '%s:%s' % (jobFrameworkId, topAncestor)

                # set the top ancestor url
                if nodeId == url.value['id']:
                    urls[topAncestor]['url'] = url.value['url']
                    urls[topAncestor]['node'] = url.value['id']

                # set the overall classification for the url
                if CLASSIFICATIONS[classification] > CLASSIFICATIONS[urls[topAncestor]['classification']]:
                    urls[topAncestor]['classification'] = classification

            else:
                urls[topAncestor] = {'classification': classification, 'url': url.value['url'], 'node': url.value['id']}

    except Exception as e:
        queryResultMessage += "Cannot process query."

    # create stats of classification totals
    for topAncestor, urlDetails in urls.iteritems():
        if urlDetails['classification'] in urlClassification:
            urlClassification[urlDetails['classification']] += 1
        else:
            urlClassification[urlDetails['classification']] = 1

    return render_response(request, 'job_details.html', \
                          {'jobs_selected': True, \
                           'job': job, \
                           'urls': urls, \
                           'urlClassification': urlClassification, \
                           'urlsDataError': queryResultMessage
                           })

@login_required
def analysis_overview(request, job_id, node):
    job = get_object_or_404(Job,id=job_id)

    queryResultMessage = ""

    # check user permission for page
    user = request.user
    if not user.is_superuser and job.owner is not user and not job.is_public:
        return HttpResponseRedirect('/nopermission/')

    # select couchdb
    try:
        couch = Server(settings.COUCHDB_SERVER)
        db = couch[settings.COUCHDB_NAME]
    except Exception as e:
        queryResultMessage = str(e) + ". "

    # get url summary
    topAncestor = int(node.split(":")[1])
    searchValues = [topAncestor, "%s" % job.frameworkid]
    summary = {}
    urls = {}
    nodes = []

    try:
        for result in db.view('url_summary_of_url_tree/view', key=searchValues ):
            summary['subpagesCount'] = result.value['subpagesCount']
            summary['classification'] = result.value['classification']
            summary['url'] = result.value['url']
    except Exception as e:
        queryResultMessage += "Cannot process query(1)."

    if 'url' not in summary or not summary['url']:
        raise Http404

    # create nodes and urls list
    try:
        for result in db.view('url_summary_of_url_tree/view', key=searchValues, reduce='false' ):
            nodes.append(result.value['id'])
            urls[result.value['id']] = {'url': result.value['url'], 'classification': 'UNKNOWN'}
    except Exception as e:
        queryResultMessage += "Cannot process query(2). "

    analyzers = {}
    # create lists:
    # - of analyzers with classification, summarized over all subpages per analyzer
    # - of all sub URLs that were crawled
    try:
        for result in db.view('analysis/by_node', keys=nodes ):
            if 'classification' in result.value:
                analysisClassification = result.value['classification'].upper()

                # analyzers list
                if ( analyzers.has_key(result.value['analyzer']) ):
                    if ( CLASSIFICATIONS[analysisClassification] > CLASSIFICATIONS[analyzers[result.value['analyzer']]] ):
                        analyzers[result.value['analyzer']] = analysisClassification
                else:
                    analyzers[result.value['analyzer']] = analysisClassification

                # URLs list
                if urls.has_key(result.key):
                    if ( CLASSIFICATIONS[analysisClassification] > CLASSIFICATIONS[urls[result.key]['classification']] ):
                        urls[result.key]['classification'] = analysisClassification

    except Exception as e:
        queryResultMessage += "Cannot process query(3). %s " % e

    return render_response(request, 'analysis_overview.html', \
                          {'jobs_selected': True, \
                           'job': job, \
                           'analyzers' : analyzers, \
                           'urlSummary': summary, \
                           'node': node, \
                           'urls': urls, \
                           'urlsDataError': queryResultMessage})

@login_required
def analysis_by_analyzer(request, job_id, node, analyzer):
    job = get_object_or_404(Job, id=job_id)

    queryResultMessage = ""

    # check user permission for page
    user = request.user
    if not user.is_superuser and job.owner is not user and not job.is_public:
        return HttpResponseRedirect('/nopermission/')

    # select couchdb
    try:
        couch = Server(settings.COUCHDB_SERVER)
        db = couch[settings.COUCHDB_NAME]
    except Exception as e:
        queryResultMessage = str(e) + ". "

    # get urls
    topAncestor = int(node.split(":")[1])
    searchValues = [topAncestor, "%s" % job.frameworkid]
    urls = {}
    urlsByAnalyzer = {}
    topLevelUrl = ''
    try:
        for result in db.view('url_summary_of_url_tree/view', key=searchValues, reduce='false' ):
            url = { 'column1': result.value['url'] }
            analysisNode = "%s:%s" % (result.value['id'], analyzer)
            urls[analysisNode] = url

            if result.value['id'] == node:
                topLevelUrl = result.value['url']

        for result in db.view('analysis/by_id_classification', keys=urls.keys()):
            urlsByAnalyzer[result.id] = urls[result.id]
            urlsByAnalyzer[result.id]['classification'] = result.value

    except Exception as e:
        queryResultMessage = "Cannot process query(1)."

    return render_response(request, 'analysis_by_analyzer.html', \
                          {'jobs_selected': True, \
                           'job': job, \
                           'currentPage': analyzer, \
                           'topLevelUrl': topLevelUrl, \
                           'node': node, \
                           'tableData': urlsByAnalyzer, \
                           'urlsDataError': queryResultMessage})

@login_required
def analysis_by_url(request, job_id, node, subnode):
    job = get_object_or_404(Job, id=job_id)

    queryResultMessage = ''
    db = None
    topLevelUrl = ''
    analyzedUrl = ''
    analyzers = {}

    # check user permission for page
    user = request.user
    if not user.is_superuser and job.owner is not user and not job.is_public:
        return HttpResponseRedirect('/nopermission/')

    # select couchdb
    try:
        couch = Server(settings.COUCHDB_SERVER)
        db = couch[settings.COUCHDB_NAME]
    except Exception as e:
        queryResultMessage = str(e) + '. '

    if db:
        try:
            topLevelUrl = db[node]['url_original']
        except:
            queryResultMessage += 'Could retrieve parent url info. '

        try:
            analyzedUrlDetails = db[subnode]
        except:
            analyzedUrlDetails = {}
            queryResultMessage += 'Could retrieve parent url info. '

        analyzedUrl = analyzedUrlDetails['url_original'] if 'url_original' in analyzedUrlDetails else ''

        try:
            for result in db.view('analysis/by_node', key=subnode ):
                if 'classification' in result.value:
                    analyzers[result.id] = { 'column1': result.value['analyzer'], 'classification': result.value['classification'].upper() }
                else:
                    analyzers[result.id] = { 'column1': result.value['analyzer'] }
        except Exception as e:
            queryResultMessage += "Cannot process query(3). %s " % e

    return render_response(request, 'analysis_by_url.html', \
                          {'jobs_selected': True, \
                           'job': job, \
                           'topLevelUrl': topLevelUrl, \
                           'node': node, \
                           'currentPage': analyzedUrl, \
                           'tableData': analyzers, \
                           'urlsDataError': queryResultMessage})

@login_required
def statistics_page(request):

    db = None
    queryResultMessage = ''

    # select couchdb
    try:
        couch = Server(settings.COUCHDB_SERVER)
        db = couch[settings.COUCHDB_NAME]
    except Exception as e:
        queryResultMessage = str(e) + '. '

    urlStatistics = {}
    urlStatistics['total'] = 0
    if db:
        for classification in ['benign', 'obfuscated', 'malicious', 'unknown', 'suspicious', 'unclassified']:
            try:
                for result in db.view('url_classification_count/view', key=classification ):
                    urlStatistics[classification] = result.value

            except Exception as e:
                queryResultMessage += "Error: %s \n" % e

    timelineTotalUrls = {}
    timelineAvgUrlPerMinute = {}
    try:
        for result in db.view('url_all_urls/view', group='true' ):
            urlStatistics['total'] += result.value
            job = Job.objects.filter(frameworkid=result.key, status=Job.COMPLETED_STATUS)
            if job.exists() and job[0].finished:
                numberOfUrls = result.value

                duration = job[0].finished - job[0].started
                avgUrlPerMinute = ( numberOfUrls / float(duration.seconds) ) * 60

                timeline = job[0].started
                for i in range( ( duration.seconds / 60 ) ):
                    timeline += timedelta(minutes=1)

                    roundedTimeline = datetime(timeline.year, timeline.month, timeline.day, timeline.hour, timeline.minute)
                    timestamp = calendar.timegm(roundedTimeline.timetuple())

                    if timestamp in timelineTotalUrls:
                        timelineTotalUrls[timestamp] += numberOfUrls
                        timelineAvgUrlPerMinute[timestamp] += avgUrlPerMinute
                    else:
                        timelineTotalUrls[timestamp] = numberOfUrls
                        timelineAvgUrlPerMinute[timestamp] = avgUrlPerMinute

                timeline += timedelta(minutes=1)
                roundedTimeline = datetime(timeline.year, timeline.month, timeline.day, timeline.hour, timeline.minute)
                timestamp = calendar.timegm(roundedTimeline.timetuple())

                if timestamp not in timelineTotalUrls:
                    timelineTotalUrls[timestamp] = 0
                    timelineAvgUrlPerMinute[timestamp] = 0
    except Exception as e:
        queryResultMessage += "Error: %s \n" % e

    timestampNow = calendar.timegm(datetime.now().timetuple())
    if timestampNow not in timelineTotalUrls:
        timelineTotalUrls[timestampNow] = 0
        timelineAvgUrlPerMinute[timestampNow] = 0

    graphDataPointsTotalUrls = []
    for timestamp in sorted(timelineTotalUrls.keys()):
        graphDataPointsTotalUrls.append([timestamp*1000, timelineTotalUrls[timestamp]])

    graphDataPointsAvgUrlPerMinute = []
    for timestamp in sorted(timelineAvgUrlPerMinute.keys()):
        graphDataPointsAvgUrlPerMinute.append([timestamp*1000, timelineAvgUrlPerMinute[timestamp]])

    jobStatistics = {}
    jobStatistics['total'] = Job.objects.count()
    jobStatistics['completed'] = Job.objects.filter(status=Job.COMPLETED_STATUS).count()
    jobStatistics['cancelled'] = Job.objects.filter(status=Job.CANCELLED_STATUS).count()
    jobStatistics['failed'] = Job.objects.filter(status=Job.FAILED_STATUS).count()
    jobStatistics['processing'] = Job.objects.filter(status=Job.PROCESSING_STATUS).count()
    jobStatistics['unknown'] = Job.objects.filter(status__gt=Job.COMPLETED_STATUS).count()

    return render_response(request, 'statistics.html', \
                           {'statistics_selected': True, \
                            'urlStatistics': urlStatistics, \
                            'jobStatistics': jobStatistics, \
                            'totalUrlsJSON': json.dumps(graphDataPointsTotalUrls), \
                            'avgUrlsPerMinuteJSON': json.dumps(graphDataPointsAvgUrlPerMinute), \
                            'queryResultMessage': queryResultMessage
                            })

@login_required
def about_page(request):
    return render_response(request, 'about.html', {'about_selected': True})

def no_permission(request):
    return render_response(request, 'no_permission.html', {})

def logout_page(request):
    logout(request)
    return HttpResponseRedirect('/')

def switch_user(request):
    logout(request)
    try:
        sso_enabled = settings.SSO_ENABLED
        remote_user = os.getenv('REMOTE_USER') or None
    except:
        sso_enabled = False

    return login(request, 'login.html', extra_context={'sso_enabled': sso_enabled, 'remote_user': remote_user})

@login_required
def get_attachment(request, node, filename):

    # select couchdb
    try:
        couch = Server(settings.COUCHDB_SERVER)
        db = couch[settings.COUCHDB_NAME]
    except:
        return HttpResponseServerError

    attachment = db.get_attachment(node, filename)

    if attachment:
        try:
            contentType = db[node]['_attachments'][filename]['content_type']
        except:
            response = HttpResponse(attachment.read())
        else:
            response = HttpResponse(attachment.read(), content_type=contentType)

        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response
    else:
        raise Http404


# AJAX REQUESTS

@login_required
def get_analyzer_details(request):
    if request.method == u'POST' and request.is_ajax():
        returnToBrowser = {'is_success': False, 'message': '', 'details': ''}

        POST = request.POST.copy()
        if POST.has_key(u'node_id') and re.match(r'^\d+:\d+:[\w-]+$', POST['node_id']):
            node_id = POST['node_id']
            # select couchdb
            try:
                couch = Server(settings.COUCHDB_SERVER)
                db = couch[settings.COUCHDB_NAME]
            except Exception as e:
                returnToBrowser['message'] = str(e) + ". "
            else:
                details = db[node_id]['details']

                analyzerData = AnalyzerData()
                analyzerData.setNode(node_id)
                returnToBrowser['details'] = analyzerData.toHTML(details)
                returnToBrowser['is_success'] = True

        else:
            returnToBrowser['message'] = u'Cannot handle this request.'

        returnToBrowserJSON = json.dumps(returnToBrowser)

        return HttpResponse(returnToBrowserJSON, mimetype='application/json')
    else:
        raise Http404

@login_required
def disable_schedule(request):
    if request.method == u'POST' and request.is_ajax():
        returnToBrowser = {'is_success': False, 'is_disabled': None, 'message': ''}

        POST = request.POST.copy()

        if POST.has_key(u'job_id') and re.match(r'^\d+$', POST['job_id']):
            try:
                scheduledJob = Schedule.objects.get(id=POST['job_id'], is_deleted=False)
            except ObjectDoesNotExist:
                returnToBrowser['message'] = u'Schedule does not exist.'
            else:
                if scheduledJob.is_public or scheduledJob.created_by == request.user:
                    scheduledJob.is_enabled = False if scheduledJob.is_enabled == 1 else True
                    scheduledJob.save()
                    returnToBrowser['is_disabled'] = scheduledJob.is_enabled
                    returnToBrowser['is_success'] = True
                else:
                    returnToBrowser['message'] = u'You do not have permission for this action.'
        else:
            returnToBrowser['message'] = u'Cannot handle this request.'

        returnToBrowserJSON = json.dumps(returnToBrowser)

        return HttpResponse(returnToBrowserJSON, mimetype='application/json')
    else:
        raise Http404

@login_required
def delete_schedule(request):
    if request.method == u'POST' and request.is_ajax():
        returnToBrowser = {'is_success': False, 'message': ''}

        POST = request.POST.copy()

        if POST.has_key(u'job_id') and re.match(r'^\d+$', POST['job_id']):
            try:
                scheduledJob = Schedule.objects.get(id=POST['job_id'], is_deleted=False)
            except ObjectDoesNotExist:
                returnToBrowser['message'] = u'Schedule does not exist.'
            else:
                if scheduledJob.is_public or scheduledJob.created_by == request.user:
                    scheduledJob.is_deleted = True
                    scheduledJob.save()
                    returnToBrowser['is_success'] = True
                else:
                    returnToBrowser['message'] = u'You do not have permission for this action.'
        else:
            returnToBrowser['message'] = u'Cannot handle this request.'

        returnToBrowserJSON = json.dumps(returnToBrowser)

        return HttpResponse(returnToBrowserJSON, mimetype='application/json')
    else:
        raise Http404 

@login_required
def get_workflow_details(request):
    if request.method == u'POST' and request.is_ajax():
        returnToBrowser = {'is_success': False, 'message': ''}

        POST = request.POST.copy()

        if POST.has_key(u'id') and re.match(r'^\d+$', POST['id']):
            workflow = {}
            try:
                workflowObj = Workflow.objects.values('xml','uses_file_upload', 'description').get(id=POST['id'])
            except ObjectDoesNotExist:
                returnToBrowser['message'] = u'No (enabled) workflows found.'

            workflow['xml'] = workflowObj['xml']
            workflow['uses_file_upload'] = workflowObj['uses_file_upload']
            workflow['description'] = workflowObj['description']
            returnToBrowser['is_success'] = True
            returnToBrowser['workflow'] = workflow
        else:
            returnToBrowser['message'] = u'Cannot handle this request.'

        returnToBrowserJSON = json.dumps(returnToBrowser)

        return HttpResponse(returnToBrowserJSON, mimetype='application/json')
    else:
        raise Http404
