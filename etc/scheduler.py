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

import sys
import os
import re
import time
import itertools
import logging.config
from croniter import croniter

from paramiko import SSHException, PasswordRequiredException, SFTPClient, Transport, RSAKey, DSSKey

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
os.environ["DJANGO_SETTINGS_MODULE"]="web.settings"

from django.conf import settings
from django.db import transaction
from django.db.models import Q

sys.path.append(settings.COMMUNICATION_LIB)
sys.path.append(settings.ALIASES_LIB)

from daemon import Daemon
from aliases import Aliases
from hsn2bus import Bus
from hsn2bus import BusException
from hsn2bus import BusTimeoutException
from hsn2cmd import CommandDispatcher, CommandDispatcherMessage
from Jobs_pb2 import JobFinished

from web.app.models import Schedule, Job
from web.app.tools import ConfigParser, datetime

from apscheduler.scheduler import Scheduler

class WorkflowNotDeployedException(Exception):
    pass

class SchedulerDaemon(Daemon):

    def __init__(self, pid, config):
        super( SchedulerDaemon, self ).__init__(pid)
        self.config = config

        # set DaemonArgs for CommandDispatcher
        daemonArgs = DaemonArgs(config)

        # setup logger
        self.logger = None
        if os.path.exists(daemonArgs.log_file):
            logging.config.fileConfig(daemonArgs.log_file)
            self.logger = logging.getLogger('framework')

        # sftp settings
        self.sftpHost = self.config.get("sftp", "host")
        self.sftpPort = int(self.config.get("sftp", "port"))
        self.sftpRemotePath = self.config.get("sftp", "remote_path")
        self.sftpUsername = self.config.get("sftp", "username")
        self.sftpPassword = self.config.get("sftp", "password") or None
        self.sftpPrivateKey = self.config.get("sftp", "pkey") or None
        self.sftpPrivateKeyPassword = self.config.get("sftp", "pkey_password") or None
        self.sftpPrivateKeyType = self.config.get("sftp", "pkey_type") or None

        if self.sftpPrivateKeyType.lower() != 'rsa' \
            and self.sftpPrivateKeyType.lower() != 'dss':
            self.sftpPrivateKeyType = None

        self.jobSubmitInterval = int(self.config.get("scheduler", "jobsubmit_interval")) or 10
        self.jobCleanupInterval = int(self.config.get("scheduler", "jobcleanup_interval")) or 30
        
        self.scheduler = Scheduler(daemonic=True)
        self.cronScheduleSequence = ('minute', 'hour', 'day', 'month', 'day_of_week')
    
    @transaction.commit_on_success
    def saveJob(self, status, frameworkJobId, scheduledJob):
        now = datetime.now()
        newJob = None

        #create new job
        if frameworkJobId is not None:
            newJob, created = Job.objects.get_or_create( frameworkid=frameworkJobId )
            newJob.name = scheduledJob.job_name
            newJob.started = now
            newJob.workflow = scheduledJob.workflow
            newJob.is_public = scheduledJob.is_public
            newJob.owner = scheduledJob.created_by
            newJob.schedule = scheduledJob
            newJob.status = status
        else:
            newJob = Job(
                        name=scheduledJob.job_name,
                        started = now,
                        workflow = scheduledJob.workflow,
                        is_public = scheduledJob.is_public,
                        owner = scheduledJob.created_by,
                        schedule = scheduledJob,
                        status = status
                        )
        newJob.save()

    @transaction.commit_on_success
    def submitJobToFramework(self, **kwargs):
        jobCommand = 'job'
        
        daemonArgs = DaemonArgs(self.config)
        daemonArgs.command = jobCommand
        unScheduledJob = kwargs['unScheduledJob']
        
        is_fileFeeder = False
        fileFeederUploadedFile = None
        del daemonArgs.param[:]

        # go through all parameters
        for parameter in unScheduledJob.parameters.all():

            # add parameter to daemonArgs.param
            if parameter.service and parameter.param_key and parameter.param_value:

                # check if a file feeder is used
                if parameter.service == settings.FILE_FEEDER_ID:
                    is_fileFeeder = True
                    fileFeederUploadedFile = parameter.param_value

                    remoteFeederFile = os.path.join(self.sftpRemotePath, parameter.param_value)
                    parameterString = '%s.%s=%s' % ( parameter.service, parameter.param_key, remoteFeederFile )
                else:
                    parameterString = '%s.%s=%s' % ( parameter.service, parameter.param_key, parameter.param_value )

                self.logger.debug("add parameter string: %s" % parameterString)
                daemonArgs.param.append([parameterString])

        # in case of a filefeeder upload file to framework server
        if is_fileFeeder:
            self.logger.debug("is file feeder")
            sftp = None
            transport = None
            try:
                transport = Transport((self.sftpHost, self.sftpPort))
                if self.sftpPassword:
                    transport.connect(username=self.sftpUsername, password=self.sftpPassword)
                else:
                    privateKey = None
                    if self.sftpPrivateKeyType and self.sftpPrivateKeyType.lower() == 'rsa':
                        privateKey = RSAKey.from_private_key_file(self.sftpPrivateKey, password=self.sftpPrivateKeyPassword )
                    if self.sftpPrivateKeyType and self.sftpPrivateKeyType.lower() == 'dss':
                        privateKey = DSSKey.from_private_key_file(self.sftpPrivateKey, password=self.sftpPrivateKeyPassword )

                    transport.connect(username=self.sftpUsername, pkey=privateKey)

                sftp = SFTPClient.from_transport(transport)

                filePath = os.path.join( settings.MEDIA_ROOT, fileFeederUploadedFile )
                remotePath = os.path.join( self.sftpRemotePath, fileFeederUploadedFile )

                self.logger.debug("uploading file from %s to %s on remote machine" % (filePath, remotePath))

                sftp.put(filePath, remotePath)
#                            sftp.put(filePath, remotePath, confirm=False)
                sftp.chmod( remotePath, 0644 )

                self.logger.debug("put OK")

            except IOError as e:
                self.logger.error("IOError: %s. Will continue with next scheduled job." % e)
                self.saveJob(Job.FAILED_STATUS, None, unScheduledJob)
            except PasswordRequiredException as e:
                self.logger.error("PasswordRequiredException: %s. Will continue with next scheduled job." % e)
                self.saveJob(Job.FAILED_STATUS, None, unScheduledJob)
            except SSHException as e:
                self.logger.error("SSH Exception: %s. Will continue with next scheduled job." % e)
                self.saveJob(Job.FAILED_STATUS, None, unScheduledJob)
            except Exception as e:
                self.logger.error("Unkown SFTP problem. Will continue with next scheduled job. %s" % e)
                self.saveJob(Job.FAILED_STATUS, None, unScheduledJob)
            finally:
                if sftp is not None:
                    sftp.close()
                if transport is not None:
                    transport.close()
                
        # set job workflow
        daemonArgs.jd_workflow = unScheduledJob.workflow.name

        frameworkJobId = None
        
        try:
            setattr(daemonArgs, jobCommand, 'submit')
            frameworkJobId = self.sendFrameworkCommand(jobCommand, daemonArgs)
            self.saveJob(Job.PROCESSING_STATUS, frameworkJobId, unScheduledJob)
        except WorkflowNotDeployedException:
            # The workflow is not deployed in the framework. To prevent the scheduler retrying continuously
            # we disable this job
            unScheduledJob.status = Schedule.DEACTIVATE_STATUS
            unScheduledJob.save()
        except:
            self.saveJob(Job.FAILED_STATUS, None, unScheduledJob)
        finally:
            daemonArgs.clean(jobCommand)
        
        if unScheduledJob.scheduled_start is not None:
            unScheduledJob.status = Schedule.DEACTIVATED_STATUS
            unScheduledJob.save()
        
    def updateProcessingJobs(self):
        jobCommand = 'job'
        processingJobs = Job.objects.filter(status=Job.PROCESSING_STATUS)
        
        daemonArgs = DaemonArgs(self.config)
        
        if len(list(processingJobs)) != 0:
            jobs_dict = {}
            try:
                setattr(daemonArgs, jobCommand, 'list')
                jobs_dict = self.sendFrameworkCommand(jobCommand, daemonArgs)
            except:
                return
            finally:
                daemonArgs.clean(jobCommand)

            for processingJob in processingJobs:
                if processingJob.frameworkid in jobs_dict \
                and int(processingJob.status) != int(jobs_dict[processingJob.frameworkid]):
                    
                    try:
                        setattr(daemonArgs, jobCommand, 'details')
                        setattr(daemonArgs, 'gjd_id', processingJob.frameworkid)
                        job_details = self.sendFrameworkCommand(jobCommand, daemonArgs)
                    except:
                        continue
                    finally:
                        daemonArgs.clean(jobCommand)
                        daemonArgs.clean('gjd_id')
                        
                    processingJob.status = jobs_dict[processingJob.frameworkid]
                    processingJob.finished = job_details['job_end_time']
                    processingJob.save()
                elif processingJob.frameworkid not in jobs_dict:
                    processingJob.status = Job.COMPLETED_STATUS
                    processingJob.finished = None
                    processingJob.save()

    def checkJobs(self):
        scheduledJobs = self.scheduler.get_jobs()
        
        # remove scheduled jobs which are set to be deleted or deactivated
        deleteAndDeactivateJobs = Schedule.objects.filter( Q(status=Schedule.DELETE_STATUS) | Q(status=Schedule.DEACTIVATE_STATUS) )
        for deleteAndDeactivateJob in deleteAndDeactivateJobs:
            for scheduledJob in scheduledJobs:
                if scheduledJob.name == deleteAndDeactivateJob.job_name:
                    self.scheduler.unschedule_job(scheduledJob)
            deleteAndDeactivateJob.status = Schedule.DEACTIVATED_STATUS\
                if deleteAndDeactivateJob.status == Schedule.DEACTIVATE_STATUS\
                else Schedule.DELETED_STATUS

            deleteAndDeactivateJob.save()
        
        # add/update unscheduled jobs
        split_re  = re.compile("\s+")
        unScheduledJobs = Schedule.objects.filter( Q(status=Schedule.NEW_STATUS) | Q(status=Schedule.UPDATE_STATUS) )
        for unScheduledJob in unScheduledJobs:
            
            if unScheduledJob.status == Schedule.UPDATE_STATUS:
                for scheduledJob in scheduledJobs:
                    if scheduledJob.name == unScheduledJob.job_name:
                        self.scheduler.unschedule_job(scheduledJob)
            
            if unScheduledJob.scheduled_start is not None:
                schedule = { 'kwargs': { 'unScheduledJob': unScheduledJob }, 'name': unScheduledJob.job_name }
                
                try:
                    newJob = self.scheduler.add_date_job(self.submitJobToFramework, unScheduledJob.scheduled_start, **schedule)
                    self.logger.debug( 'Job will run on %s' % newJob.next_run_time )
                except Exception as e:
                    self.logger.error("Unknown error while submitting jobs to framework: %s" % str(e))
                    raise Exception
                else:
                    unScheduledJob.status = Schedule.ACTIVE_STATUS
                    unScheduledJob.save()
            
            else:
                cronList = split_re.split(unScheduledJob.cron_expression)
                schedule = dict(itertools.izip(self.cronScheduleSequence, cronList))
                
                schedule['kwargs'] = { 'unScheduledJob': unScheduledJob }
                schedule['name'] = unScheduledJob.job_name
                
                try:
                    newJob = self.scheduler.add_cron_job(self.submitJobToFramework, **schedule)
                    self.logger.debug( 'First run of job will be on %s' % newJob.next_run_time )
                except Exception as e:
                    self.logger.error("Unknown error while submitting jobs to framework: %s" % str(e))
                    raise Exception
                else:
                    unScheduledJob.status = Schedule.ACTIVE_STATUS
                    unScheduledJob.save()
                
    def cleanup(self):
        try:
            self.updateProcessingJobs()
        except Exception as e:
            self.logger.error("Unknown error while updating processing jobs: %s" % str(e))
            raise Exception
        
    def onNotification(self, eventType, body):
        if eventType == 'JobFinished':
            
            # sleep is added, because a failing job can be quicker than 
            # Django save the frameworkid of that job
            time.sleep(1) 
            event = JobFinished()
            event.ParseFromString(body)
            
            self.logger.debug('Job with ID %s is finished with status %s', str(event.job), str(event.status))

            Job.objects.update()
            finishedJob = Job.objects.get(frameworkid=event.job)
            finishedJob.status = event.status
            finishedJob.finished = datetime.now()
            finishedJob.save()
        return True
        
    def run(self):
        self.logger.info('Started scheduler')

        # add active schedules to scheduler
        split_re  = re.compile("\s+")
        scheduledJobs = Schedule.objects.filter( status=Schedule.ACTIVE_STATUS )

        for scheduledJob in scheduledJobs:

            if scheduledJob.scheduled_start is not None:
                schedule = { 'kwargs': { 'unScheduledJob': scheduledJob }, 'name': scheduledJob.job_name }
                
                try:
                    newJob = self.scheduler.add_date_job(self.submitJobToFramework, scheduledJob.scheduled_start, **schedule)
                except Exception as e:
                    self.logger.error("Unknown error while submitting jobs to framework: %s" % str(e))
                    raise Exception
            else:
                cronList = split_re.split(scheduledJob.cron_expression)
                schedule = dict(itertools.izip(self.cronScheduleSequence, cronList))
                
                schedule['kwargs'] = { 'unScheduledJob': scheduledJob }
                schedule['name'] = scheduledJob.job_name
               
                try:
                    newJob = self.scheduler.add_cron_job(self.submitJobToFramework, **schedule)
                except Exception as e:
                    self.logger.error("Unknown error while submitting jobs to framework: %s" % str(e))
                    raise Exception

        # add job scheduling mechanism and cleanup to scheduler and start scheduler 
        try:
            self.scheduler.add_interval_job(self.checkJobs, seconds=self.jobSubmitInterval)
            self.scheduler.add_interval_job(self.cleanup, minutes=self.jobCleanupInterval)
            self.scheduler.start()
        except Exception as e:
            self.logger.error("Unknown error while initializing scheduler: %s" % str(e))
            raise Exception

        # initialize bus instance for receiving job notifications
        try:
            notificationBus = Bus.createConfigurableBus(self.logger, self.config, 'notifications')
            notificationBus.openFwChannel()
            notificationBus.attachToMonitoring(self.onNotification)
            notificationBus.close()
        except BusException, e:
            self.logger.error("Cannot connect to HSN2 Bus because '%s'" % e)
            raise Exception
        except BusTimeoutException, e:
            self.logger.error("Response timeout")
            raise Exception
        except Exception as e:
            self.logger.error("Unknown error: %s" % str(e))
            raise Exception
        
    def sendFrameworkCommand(self, command, daemonArgs):
        frameworkResponse = None
        aliases = Aliases()
        try:
            fwkBus = Bus.createConfigurableBus(self.logger, self.config, 'cli')
            fwkBus.openFwChannel()
            dispatcher = CommandDispatcher(fwkBus, self.logger, daemonArgs, self.config, False)
            frameworkResponse = dispatcher.dispatch(command, aliases)
        except BusException, e:
            self.logger.error("Cannot connect to HSN2 Bus because '%s'" % e)
            raise Exception
        except BusTimeoutException, e:
            self.logger.error("Response timeout")
            raise Exception
        except CommandDispatcherMessage as e:
            if str(e).find(daemonArgs.workflow_not_deployed) != -1:
                self.logger.warn("Framework reports the Workflow is not deployed.")
                raise WorkflowNotDeployedException
            else:
                self.logger.error("Error response from framework: %s" % str(e))
                raise CommandDispatcherMessage
        except Exception as e:
            self.logger.error("Unknown error while connecting to framework: %s" % str(e))
            raise Exception

        fwkBus.close()

        return frameworkResponse


class DaemonArgs(object):

    def __init__(self, config):
        self.command = ''
        self.jd_workflow = None
        self.param = []
        self.log_file = config.get("scheduler", "log_file")
        self.log_level = config.get("scheduler", "log_level")
        self.workflow_not_deployed = config.get("scheduler", "workflow_not_deployed")

    def clean(self, arg):
        try:
            delattr(self, arg)
        except:
            pass


if __name__ == "__main__":

    config = ConfigParser()
    configFile = os.path.join(os.path.dirname(__file__), 'scheduler.conf')

    if os.path.exists(configFile):
        config.readfp(open(configFile))
    else:
        print "could not find configuration file at %s" % configFile
        sys.exit()

    log_config = config.get("scheduler", "log_file")
    if not os.path.exists(log_config):
        print "could not find log configuration file at %s" % log_config
        sys.exit()

    pid = config.get("scheduler", "pid")

    daemon = SchedulerDaemon(pid, config)
    
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s start|stop|restart" % sys.argv[0]
        sys.exit(2)
