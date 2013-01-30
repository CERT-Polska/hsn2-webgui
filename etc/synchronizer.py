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
import datetime
from ConfigParser import ConfigParser
import xml.etree.ElementTree as elementTree
import logging.config
from logging import getLogger

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
os.environ["DJANGO_SETTINGS_MODULE"]="web.settings"

from django.conf import settings

sys.path.append(settings.COMMUNICATION_LIB)
sys.path.append(settings.ALIASES_LIB)

from daemon import Daemon
from aliases import Aliases
from hsn2bus import Bus
from hsn2bus import BusException
from hsn2bus import BusTimeoutException
from hsn2cmd import CommandDispatcher, CommandDispatcherMessage

from web.app.models import Workflow

class Synchronizer (object):

    def __init__(self, config):
        self.config = config

        # set DaemonArgs for CommandDispatcher
        self.daemonArgs = DaemonArgs(config)

        # setup logger
        self.logger = None
        if os.path.exists(self.daemonArgs.log_file):
            logging.config.fileConfig(self.daemonArgs.log_file)
        self.logger = logging.getLogger('webgui')

    def syncWorkflows(self):
        workflowCommand = 'workflow'
        setattr(self.daemonArgs, 'enabled', False)
        setattr(self.daemonArgs, workflowCommand, 'list')
        self.daemonArgs.command = workflowCommand
        workflows = []
        allRevisionNumbers = []
        try:
            workflows = self.sendFrameworkCommand(workflowCommand)
        except:
            print "Retrieving workflows list failed"
        finally:
            self.daemonArgs.clean('enabled')

        for workflow in workflows:

            self.daemonArgs.jd_workflow = workflow.name
            setattr(self.daemonArgs, workflowCommand, 'history')
            revisions = []
            try:
                revisions = self.sendFrameworkCommand(workflowCommand)
            except:
                print "Retrieving revisions failed"

            for rev in revisions:
                allRevisionNumbers.append(rev.revision)
                setattr(self.daemonArgs, 'revision', rev.revision)
                setattr(self.daemonArgs, workflowCommand, 'status')

                revisionDetails = None
                try:
                     revisionDetails = self.sendFrameworkCommand(workflowCommand)
                except:
                    print "Retrieving revision details failed"

                workflowXml = ''
                self.daemonArgs.jd_workflow = workflow.name
                setattr(self.daemonArgs, workflowCommand, 'get')
                setattr(self.daemonArgs, 'file', None)

                try:
                    workflowXml = self.sendFrameworkCommand(workflowCommand)
                except:
                    print "Retrieving workflow XML failed"
                finally:
                    self.daemonArgs.clean('revision')
                    self.daemonArgs.clean('file')

                # remove tabs and normalize newlines of workflow description
                workflowDescription = revisionDetails.description
                workflowDescription = re.sub('\n+', '\n', workflowDescription)
                workflowDescription = re.sub('^\n+', '', workflowDescription)
                workflowDescription = re.sub('\t*', '', workflowDescription)

                # Check if workflow has a feeder service that uses files as input.
                # Check is made possible by the convention of setting id=feeder
                # for a feeder service which uses files as input.
                useFileUpload = False
                if workflowXml:
                    try:
                        workflowTree = elementTree.fromstring(workflowXml)
                    
                        for serviceElement in workflowTree.findall('process/service'):
                            if 'id' in serviceElement.attrib and serviceElement.attrib['id'] == settings.FILE_FEEDER_ID:
                                useFileUpload = True
                    except Exception as e:
                        print 'Parsing error for workflow %s: %s' % ( workflow.name, str(e) )
                        continue
                    
                newWorkflow, created = Workflow.objects.get_or_create( revision=rev.revision )
                newWorkflow.name = workflow.name
                newWorkflow.date = datetime.datetime.fromtimestamp(rev.mtime)
                newWorkflow.enabled = revisionDetails.enabled
                newWorkflow.description = workflowDescription
                newWorkflow.xml = workflowXml
                newWorkflow.uses_file_upload = useFileUpload
                newWorkflow.save()
            
        # disable workflows which are not on the framework
        localWorkflows = Workflow.objects.all()
        for localWorkflow in localWorkflows:
            if localWorkflow.revision not in allRevisionNumbers:
                localWorkflow.enabled = False
                localWorkflow.save()
            

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

    synchronizer = Synchronizer(config)

    if len(sys.argv) == 2:
        if 'workflows' == sys.argv[1]:
            synchronizer.syncWorkflows()
        else:
            print "Unknown command"
            sys.exit(2)
        sys.exit(0)
    else:
        print "usage: %s workflows" % sys.argv[0]
        sys.exit(2)
