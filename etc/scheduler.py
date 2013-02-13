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
import time
import textwrap
import logging.config

from dateutil.rrule import rrule, MINUTELY, HOURLY, DAILY, WEEKLY, MONTHLY
from paramiko import SSHException, PasswordRequiredException, SFTPClient, Transport, RSAKey, DSSKey

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
os.environ["DJANGO_SETTINGS_MODULE"]="web.settings"

from django.conf import settings
from django.db import transaction

sys.path.append(settings.COMMUNICATION_LIB)
sys.path.append(settings.ALIASES_LIB)

from daemon import Daemon
from aliases import Aliases
from hsn2bus import Bus
from hsn2bus import BusException
from hsn2bus import BusTimeoutException
from hsn2cmd import CommandDispatcher, CommandDispatcherMessage

from web.app.models import Schedule, Job
from web.app.tools import ConfigParser, datetime

class WorkflowNotDeployedException(Exception):
    pass

class SchedulerDaemon(Daemon):

    def __init__(self, pid, config):
        super( SchedulerDaemon, self ).__init__(pid)
        self.config = config

        # set DaemonArgs for CommandDispatcher
        self.daemonArgs = DaemonArgs(config)

        # setup logger
        self.logger = None
        if os.path.exists(self.daemonArgs.log_file):
            logging.config.fileConfig(self.daemonArgs.log_file)
            self.logger = logging.getLogger('framework')
        else:
            pass

        self.selectScheduledJobsSQL = textwrap.dedent("""
            SELECT * FROM app_schedule
            WHERE (
                   last_submit IS NULL
                OR ( frequency = %s AND ( NOW() > ADDTIME(last_scheduled, '00:30:00') OR last_scheduled IS NULL ) )
                OR ( frequency = %s AND ( NOW() > ADDTIME(last_scheduled, '01:00:00') OR last_scheduled IS NULL ) )
                OR ( frequency = %s AND ( NOW() > ADDTIME(last_scheduled, '24:00:00') OR last_scheduled IS NULL ) )
                OR ( frequency = %s AND ( NOW() > ADDTIME(last_scheduled, '7 00:00:00') OR last_scheduled IS NULL )  )
                OR ( frequency = %s AND ( NOW() > DATE_ADD(last_scheduled, INTERVAL 1 MONTH) OR last_scheduled IS NULL ) )
            )
            AND ( scheduled_start IS NULL OR scheduled_start < NOW() )
            AND is_enabled = TRUE
            ORDER BY frequency, last_scheduled""" % \
            (Schedule.HALF_HOURLY_FREQUENCY, Schedule.HOURLY_FREQUENCY, Schedule.DAILY_FREQUENCY, Schedule.WEEKLY_FREQUENCY, Schedule.MONTHLY_FREQUENCY))

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

        self.pingInterval = int(self.config.get("scheduler", "ping_interval")) or 20
        self.pingCountDown = 0
        self.jobListInterval = int(self.config.get("scheduler", "joblist_interval")) or 20
        self.jobListCountDown = self.jobListInterval

        self.is_alive = False

    def do_actions(self):
            jobCommand = 'job'

            # SCHEDULER ACTION: update jobs with status Processing
            processingJobs = Job.objects.filter(status=Job.PROCESSING_STATUS)
            if len(list(processingJobs)) != 0:
                if self.jobListCountDown == 0:
                    self.jobListCountDown = self.jobListInterval
                    jobs_dict = {}
                    try:
                        setattr(self.daemonArgs, jobCommand, 'list')
                        jobs_dict = self.sendFrameworkCommand(jobCommand)
                    except:
                        return
                    finally:
                        self.daemonArgs.clean(jobCommand)

                    for processingJob in processingJobs:
                        if processingJob.frameworkid in jobs_dict \
                        and int(processingJob.status) != int(jobs_dict[processingJob.frameworkid]):
                            
                            try:
                                setattr(self.daemonArgs, jobCommand, 'details')
                                setattr(self.daemonArgs, 'gjd_id', processingJob.frameworkid)
                                job_details = self.sendFrameworkCommand(jobCommand)
                            except:
                                return
                            finally:
                                self.daemonArgs.clean(jobCommand)
                                self.daemonArgs.clean('gjd_id')
                                
                            processingJob.status = jobs_dict[processingJob.frameworkid]
                            processingJob.finished = job_details['job_end_time']
                            processingJob.save()
                        elif processingJob.frameworkid not in jobs_dict:
                            processingJob.status = Job.COMPLETED_STATUS
                            processingJob.finished = None
                            processingJob.save()
                    self.pingCountDown = self.pingInterval
                else:
                    self.jobListCountDown = self.jobListCountDown - 1

            # SCHEDULER ACTION: submit jobs which are scheduled to run
            scheduledJobs = Schedule.objects.raw(self.selectScheduledJobsSQL)
            if len(list(scheduledJobs)) != 0:

                self.daemonArgs.command = jobCommand

                self.logger.debug("%s jobs to submit..." % len(list(scheduledJobs)))

                for scheduledJob in scheduledJobs:
                    self.logger.debug("job: %s" % scheduledJob.job_name )
                    is_fileFeeder = False
                    fileFeederUploadedFile = None
                    del self.daemonArgs.param[:]

                    # go through all parameters
                    for parameter in scheduledJob.parameters.all():

                        # add parameter to self.daemonArgs.param
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
                            self.daemonArgs.param.append([parameterString])

                    # in case of a filefeeder upload file to framework server
                    if is_fileFeeder:
                        self.logger.debug("is file feeder")
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
#TODO: check os.path.exists(filePath)
                            filePath = os.path.join( settings.MEDIA_ROOT, fileFeederUploadedFile )
                            remotePath = os.path.join( self.sftpRemotePath, fileFeederUploadedFile )

                            self.logger.debug("uploading file from %s to %s on remote machine" % (filePath, remotePath))

                            sftp.put(filePath, remotePath)
#                            sftp.put(filePath, remotePath, confirm=False)
                            sftp.chmod( remotePath, 0644 )

                            self.logger.debug("put OK")

                        except IOError as e:
                            self.logger.error("IOError: %s. Will continue with next scheduled job." % e)
                            continue
                        except PasswordRequiredException as e:
                            self.logger.error("PasswordRequiredException: %s. Will continue with next scheduled job." % e)
                            continue
                        except SSHException as e:
                            self.logger.error("SSH Exception: %s. Will continue with next scheduled job." % e)
                            continue
                        except Exception as e:
                            self.logger.error("Unkown SFTP problem. Will continue with next scheduled job. %s" % e)
                            continue
                        finally:
                            sftp.close()
                            transport.close()

                    # set job workflow
                    self.daemonArgs.jd_workflow = scheduledJob.workflow.name

                    frameworkJobId = None
                    workflowDeployed = True
                    
                    try:
                        setattr(self.daemonArgs, jobCommand, 'submit')
                        frameworkJobId = self.sendFrameworkCommand(jobCommand)
                    except WorkflowNotDeployedException:
                        workflowDeployed = False
                    except:
                        break
                    finally:
                        self.daemonArgs.clean(jobCommand)
                    
                    if workflowDeployed:
                        now = datetime.now()
                        
                        # check if a job with frameworkJobId allready exists
                        # if so create a new Job in DB without frameworkJobId
                        newJob, created = Job.objects.get_or_create( frameworkid=frameworkJobId )
                        if created:
                            newJob.name = scheduledJob.job_name
                            newJob.started = now
                            newJob.workflow = scheduledJob.workflow
                            newJob.is_public = scheduledJob.is_public
                            newJob.owner = scheduledJob.created_by
                            newJob.schedule = scheduledJob
                            newJob.status = Job.PROCESSING_STATUS
                        else:
                            #TODO: a warning should be issued somewhere
                            newJob = None
                            newJob = Job(
                                        name=scheduledJob.job_name,
                                        started = now,
                                        workflow = scheduledJob.workflow,
                                        is_public = scheduledJob.is_public,
                                        owner = scheduledJob.created_by,
                                        schedule = scheduledJob,
                                        status = Job.PROCESSING_STATUS
                                        )
                        newJob.save()
    
                        # update schedule
                        scheduledJob.last_submit = now
    
                        calcFromDate = scheduledJob.last_scheduled if scheduledJob.last_scheduled \
                            else scheduledJob.scheduled_start if scheduledJob.scheduled_start \
                            else None
    
                        if calcFromDate:
                            if scheduledJob.frequency == Schedule.HALF_HOURLY_FREQUENCY:
                                scheduledJob.last_scheduled = rrule(MINUTELY, calcFromDate, interval=30).before(now, True)
                            if scheduledJob.frequency == Schedule.HOURLY_FREQUENCY:
                                scheduledJob.last_scheduled = rrule(HOURLY, calcFromDate).before(now, True)
                            if scheduledJob.frequency == Schedule.DAILY_FREQUENCY:
                                scheduledJob.last_scheduled = rrule(DAILY, calcFromDate).before(now, True)
                            elif scheduledJob.frequency == Schedule.WEEKLY_FREQUENCY:
                                scheduledJob.last_scheduled = rrule(WEEKLY, calcFromDate).before(now, True)
                            elif scheduledJob.frequency == Schedule.MONTHLY_FREQUENCY:
                                scheduledJob.last_scheduled = rrule(MONTHLY, calcFromDate).before(now, True)
    
                        scheduledJob.save()
                    else:
                        # The workflow is not deployed in the framework. To prevent the scheduler retrying continuously
                        # we disable this job
                        scheduledJob.is_enabled = False
                        scheduledJob.save()

                    self.pingCountDown = self.pingInterval

            # SCHEDULER ACTION: every Xth iteration check if framework is alive with ping command
#            if self.pingCountDown == 0 or self.jobListCountDown == 0:
#                self.pingCountDown = self.pingInterval
#                try:
#                    self.is_alive = self.sendFrameworkCommand('ping')
#                except:
#                    continue
#
#                self.logger.debug("Framework is alive: %s" % self.is_alive)
#            else:
#                self.pingCountDown = self.pingCountDown - 1

            time.sleep(1)



    def run(self):

        # daemon loop
        while True:
            self.logger.debug('whop whop whop') # pulse
            with transaction.commit_on_success():
                self.do_actions()


    def sendFrameworkCommand(self, command):

        frameworkResponse = None
        aliases = Aliases()
        try:
#            fwkBus = Bus.createConfigurableBus(self.logger, self.config, 'webgui-scheduler')
            fwkBus = Bus.createConfigurableBus(self.logger, self.config, 'cli')
            fwkBus.openFwChannel()
            disp = CommandDispatcher(fwkBus, self.logger, self.daemonArgs, self.config, False)
            frameworkResponse = disp.dispatch(command, aliases)
        except BusException, e:
            self.logger.error("Cannot connect to HSN2 Bus because '%s'" % e)
            raise Exception
        except BusTimeoutException, e:
            self.logger.error("Response timeout")
            raise Exception
        except CommandDispatcherMessage as e:
            if str(e).find(self.daemonArgs.workflow_not_deployed) != -1:
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
