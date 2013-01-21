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

from django import forms
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.forms.extras.widgets import SelectDateWidget
from django.conf import settings

from web.app.models import Schedule, Workflow
from web.app.custom.form import CustomRadioFieldRenderer

ISPUBLIC_CHOICES = ((1, 'Yes'), (0, 'No'))
SCHEDULEWHEN_CHOICES = (('now', 'Once, as soon as possible'), ('later', 'Set date, time and frequency'))


class JobForm (forms.Form):

    schedule_when = forms.ChoiceField(
                                      choices=SCHEDULEWHEN_CHOICES,
                                      widget=forms.RadioSelect(renderer=CustomRadioFieldRenderer),
                                      initial='now'
                                    )

    schedule_date = forms.DateField( required=False, widget=SelectDateWidget() )
    schedule_time = forms.TimeField(
                                     required=False,
                                     input_formats=['%H:%M'],
                                     widget=forms.TimeInput( format='%H:%M', \
                                                             attrs={'placeholder': 'HH:MM', 'class': 'width_narrow'} )
                                    )

    schedule_frequency = forms.ChoiceField(
                                            required=False,
                                            choices=Schedule.SCHEDULE_FREQUENCY,
                                            widget=forms.RadioSelect(renderer=CustomRadioFieldRenderer),
                                            initial='0'
                                           )

    job_name = forms.CharField( widget=forms.TextInput( attrs={'class': 'minwidth_200'}))

    is_public = forms.ChoiceField(
                                    choices=ISPUBLIC_CHOICES,
                                    widget=forms.RadioSelect(renderer=CustomRadioFieldRenderer),
                                    initial='1'
                                 )

    edit_processed_jobs = forms.CharField( required=False, widget=forms.HiddenInput())
    is_public_org = forms.CharField( required=False, widget=forms.HiddenInput())

    latestWorkflowsSQL = 'SELECT * FROM app_workflow WHERE name IN (SELECT name FROM app_workflow GROUP BY name HAVING date = MAX(date)) AND enabled = true order by name'

    workflow = forms.ChoiceField( 
                                  choices=[(wf.id,wf.name) for wf in Workflow.objects.raw(latestWorkflowsSQL)],
                                  widget=forms.Select( attrs={'class': 'minwidth_200'} )
                                )

    def __init__(self, *args, **kwargs):
        super(JobForm, self).__init__(*args, **kwargs)

        workflowId = args[0].get('workflow') if args else None

        selectedWorkflow = None
        if workflowId:
            try:
                selectedWorkflow = Workflow.objects.get(id=workflowId)
            except:
                pass
        else:
            try:
                selectedWorkflow = Workflow.objects.raw(self.latestWorkflowsSQL)[0:1]
            except ObjectDoesNotExist:
                pass
            else:
                if selectedWorkflow:
                    selectedWorkflow = selectedWorkflow[0]

        if selectedWorkflow:
            self.fields['workflow_description'] = forms.CharField(initial=selectedWorkflow.description, required=False)
            self.fields['workflow_xml'] = forms.CharField(initial=selectedWorkflow.xml, required=False )

            hasFeederFile = True if args and args[0].get('feeder_file') else False
            inputFieldClass = 'hide' if not selectedWorkflow.uses_file_upload or hasFeederFile else ''
            self.fields['feeder_file'] = forms.FileField(
                                                           required=False,
                                                           widget=forms.ClearableFileInput(attrs={'class':inputFieldClass})
                                                         )

    def clean(self):

            scheduleWhen = self.cleaned_data.get('schedule_when', None)
            scheduleDate = self.cleaned_data.get('schedule_date', None)
            scheduleTime = self.cleaned_data.get('schedule_time', None)
            scheduleFrequency = self.cleaned_data.get('schedule_frequency', None)
            workflowId = self.cleaned_data.get('workflow', None)

            if scheduleWhen == 'later' and \
                ( scheduleDate == None or scheduleTime == None or scheduleFrequency == None ):

                if scheduleDate == None and self._errors.get('schedule_date', None) == None:
                    self._errors['schedule_date'] = self.error_class(['When scheduling a job a date is required.'])

                if scheduleTime == None and self._errors.get('schedule_time', None) == None:
                    self._errors['schedule_time'] = self.error_class(['When scheduling a job a time is required.'])

                if scheduleFrequency == None:
                    self._errors['schedule_frequency'] = self.error_class(['When scheduling a job selecting a frequency is required.'])

            try:
                self.cleaned_data['workflow'] = Workflow.objects.get(id=workflowId)
            except ObjectDoesNotExist:
                self._errors['workflow'] = self.error_class(['Not a valid workflow, please select one from the available workflows.'])

            # check if every field of an added parameter is not blank
            parameterGroups = {}
            for inputFieldName, value in self.cleaned_data.iteritems():

                if inputFieldName.startswith('workflow_parameter'):
                    groupNumber = re.sub(r'.*?_(\d+)$', r'\1', inputFieldName)
                    if groupNumber in parameterGroups:
                        parameterGroups[groupNumber][inputFieldName] = value.strip()
                    else:
                        parameterGroups[groupNumber] = {inputFieldName: value.strip()}

            for groupNumber, parameterGroup in parameterGroups.iteritems():
                if (
                        not parameterGroup['workflow_parameter_service_%s' % groupNumber] \
                        or not parameterGroup['workflow_parameter_name_%s' % groupNumber] \
                        or not parameterGroup['workflow_parameter_value_%s' % groupNumber]
                    ) \
                    and not \
                    (
                        not parameterGroup['workflow_parameter_service_%s' % groupNumber] \
                        and not parameterGroup['workflow_parameter_name_%s' % groupNumber] \
                        and not parameterGroup['workflow_parameter_value_%s' % groupNumber]
                    ):

                    self._errors['workflow_parameter_service_%s' % groupNumber] = self.error_class(["Please specify 'service', 'name' and 'value'."])

            return self.cleaned_data
