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

from django.db import models
from django.contrib.auth.models import User

CLASSIFICATIONS = {
    'UNKNOWN': 1,
    'UNCLASSIFIED': 1,
    'BENIGN': 2,
    'OBFUSCATED': 3,
    'SUSPICIOUS': 3,
    'MALICIOUS': 4,
}


class Workflow (models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=250)
    description = models.TextField(null=True)
    enabled = models.BooleanField(default=True)
    uses_file_upload = models.BooleanField(default=False)
    revision = models.TextField()
    date = models.DateTimeField(null=True)
    xml = models.TextField()

    def __unicode__(self):
        return '%s %s %s' % (self.id, self.name, self.date )


class Schedule (models.Model):

    NEW_STATUS = 1
    UPDATE_STATUS = 2
    ACTIVE_STATUS = 3
    DEACTIVATE_STATUS = 4
    DELETED_STATUS = 5
    DELETE_STATUS = 6
    DEACTIVATED_STATUS = 7
    
    SCHEDULE_STATUS = (
                            (NEW_STATUS, 'Adding'),
                            (UPDATE_STATUS, 'Updating'),
                            (ACTIVE_STATUS, 'Active'),
                            (DEACTIVATE_STATUS, 'Deactivating'),
                            (DEACTIVATED_STATUS, 'Deactivated'),
                            (DELETED_STATUS, 'Deleted'),
                            (DELETE_STATUS, 'Deleting')
                       )

    id = models.AutoField(primary_key=True)
    created_by = models.ForeignKey(User)
    job_name = models.CharField(max_length=250)
    scheduled_start = models.DateTimeField(null=True)
    workflow = models.ForeignKey(Workflow, null=True, related_name='schedule')
    is_public = models.BooleanField(default=False)
    status = models.IntegerField(choices=SCHEDULE_STATUS)
    cron_expression = models.CharField(max_length=150, null=True)

    def __unicode__(self):
        return self.job_name


class ServiceParameter (models.Model):
    id = models.AutoField(primary_key=True)
    service = models.CharField(max_length=250)
    param_key = models.CharField(max_length=250)
    param_value = models.CharField(max_length=250)
    schedule = models.ForeignKey(Schedule, related_name='parameters')

    def clean(self):
        self.service = self.service.strip()
        self.param_key = self.param_key.strip()
        self.param_value = self.param_value.strip()

    def __unicode__(self):
        return '%s.%s=%s' % ( self.service, self.param_key, self.param_value )

class Job (models.Model):
    
    ACCEPTED_STATUS = 1 
    STARTING_STATUS = 2
    PROCESSING_STATUS = 3
    COMPLETED_STATUS = 4
    FAILING_STATUS = 5
    FAILED_STATUS = 6
    CANCELLING_STATUS = 7
    CANCELLED_STATUS = 8
  
    JOBSTATUS = (
                    (ACCEPTED_STATUS, 'ACCEPTED'),
                    (STARTING_STATUS, 'STARTING'),
                    (PROCESSING_STATUS, 'PROCESSING'),
                    (COMPLETED_STATUS, 'COMPLETED'),
                    (FAILING_STATUS, 'FAILING'),
                    (FAILED_STATUS, 'FAILED'),
                    (CANCELLING_STATUS, 'CANCELLING'),
                    (CANCELLED_STATUS, 'CANCELLED')
                 )

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=250)
    started = models.DateTimeField(null=True)
    finished = models.DateTimeField(null=True)
    owner = models.ForeignKey(User, null=True)
    workflow = models.ForeignKey(Workflow, null=True)
    is_public = models.BooleanField()
    schedule = models.ForeignKey(Schedule, null=True)
    frameworkid = models.IntegerField(unique=True, null=True)
    status = models.IntegerField(choices=JOBSTATUS, default=PROCESSING_STATUS)

    def __unicode__(self):
        return self.name
