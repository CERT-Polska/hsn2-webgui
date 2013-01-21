// Copyright (c) NASK, NCSC
// 
// This file is part of HoneySpider Network 2.0.
// 
// This is a free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

$( function () {
	
	// select a workflow
	$('#id_workflow').change( function () {
		$.post(
			'/getworkflowdetails/',
			{ id: $(this).val() },
			function (result) {
				if ( result.is_success ) {

					$('#workflow_description').text(result.workflow.description);
					$('#hid_workflow_description').val(result.workflow.description);
					$('#workflow_xml').text(result.workflow.xml)
					$('#hid_workflow_xml').val(result.workflow.xml)
 					
					if ( result.workflow.uses_file_upload ) {
						
						if ( $('#feeder_file_is_uploaded').length > 0 ) {
							$('#feeder_file_is_uploaded').show();
							$('#id_feederFileIsUsed').val('True');
						} else {
						
							if ( $('#feeder_file_upload').hasClass('hide') ) {
								$('#feeder_file_upload').removeClass('hide');
							} else {
								$('#feeder_file_upload').show();
							}
						}
					} else {
						if ( $('#feeder_file_is_uploaded').length > 0 ) {
							$('#feeder_file_is_uploaded').hide();
							$('#id_feederFileIsUsed').val('False');
						} else {
							if ( $('#feeder_file_upload').hasClass('hide') ) {
								$('#feeder_file_upload').removeClass('hide');
							}
							$('#feeder_file_upload').hide();
						}
					}
				} else {
					alert(result.message);
				}
			}, 'json'
		);
	});
	
	$('#replace_feeder_file').click( function () {
		$('#feeder_file_is_uploaded').remove();
		if ( $('#feeder_file_upload').hasClass('hide') ) {
			$('#feeder_file_upload').removeClass('hide');
		} else {
			$('#feeder_file_upload').show();
		}
		$('#id_feeder_file').after('<br><span class="label">&nbsp;</span><span class="label italic">By saving the schedule details the uploaded feeder file will not be used.</span>');
	});
	
	// show/hide workflow XML
	$('#toggle_workflow_xml').click( function () {
		if ( $('#workflow_xml').is(':hidden') ) {
			if ( $('#workflow_xml').hasClass('hide') ) {
				$('#workflow_xml')
					.css('display', 'none')
					.removeClass('hide');
			}
			$('#workflow_xml').slideDown();
		} else {
			$('#workflow_xml').slideUp();
		}
	});
	
	// show/hide scheduling options
	$('input[name="schedule_when"]').change( function () {
		
		if ( $('#id_schedule_when_1').is(':checked') ) {
			$('#span_scheduling_options').css('color', 'grey');
			$('#div_scheduling_options').slideDown();
		} else {
			$('#div_scheduling_options').slideUp();
			$('#span_scheduling_options').css('color', 'lightgrey');
		}
	});
	
	//trigger initial scheduling options state
	if ( $('#id_schedule_when_1').is(':checked') ) {
		$('#div_scheduling_options').show();
	}
	
	// save job
	$('#btn_save').click( function () {
		
		if ( 
				$('#id_edit_processed_jobs').length 
				&& $('input[name="is_public"]:checked').val() != $('#id_is_public_org').val() 
		) {
			apprise('Do you want all processed jobs to change the public/non-public status?', 
					{'verify':true, 'textYes':'Yes, also change it for all processed jobs.', 'textNo':'No, only change it for future jobs.'},
					function(result) {
						if (result) {
							$('#id_edit_processed_jobs').val("1")
							$('#form_job').submit();
						} else {
							$('#id_edit_processed_jobs').val("0")
							$('#form_job').submit();
						}
					}
			);
			
		} else {
			$('#form_job').submit();
		}
	});
	
	// add parameters
	$('#add_parameter').click( function () {
		var parametersInput = $('.parameters_div:last').clone();
		
		var parametersCount = ( 1 + parseInt(parametersInput.attr('data-parameterscount') ) );
		parametersInput.children('input').each( function () {
			
			parameterName = $(this).attr('name').replace( /(.*?_)\d+$/, '$1' + parametersCount);
			$(this)
				.val('')
				.attr({	'name': parameterName, 'id': 'id_' + parameterName });
		});

		parametersInput.children('.btn_remove_parameter').removeClass('hide');
		parametersInput.children('ul.errorlist, br').remove();
		parametersInput.attr('data-parameterscount', parametersCount);
		parametersInput.insertAfter('.parameters_div:last');
	});
	
	// remove parameter
	$('#form_job').on('click', '.btn_remove_parameter', function() {
		$(this).parent().remove();
	});
	
	// init showing file upload field
	if ( $('#id_feeder_file').hasClass('hide') == false ) {
		$('#feeder_file_upload').removeClass('hide');
	}
	$('#id_feeder_file').removeClass('hide')
	
});