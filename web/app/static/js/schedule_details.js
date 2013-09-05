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

	// click on button 'Disable schedule'
	$('#btn_disableSchedule').click( function () {
		$.post( '/schedule/disable/', 
				{ job_id: $(this).attr('data-jobid') }, 
				function (result) {
					if ( result.is_success ) {
						$('#div_jobDisabled').toggle( !result.is_disabled );
						if ( result.status != 4 && result.status != 7 ) {
							$('#div_jobDisabled').hide();
						} else {
							$('#div_jobDisabled').show();
						} 
						
						$('#btn_disableSchedule').parent('li').html('<span>Updating status</span>');

					} else {
						$('#div_errorMessage')
							.text(result.message)
							.show();
					}
				}, 
				'json'
		);
	});

	// click on button 'Delete schedule'
	$('#btn_deleteSchedule').click( function () {
		
		if ( confirm( 'Are you sure you want to delete this schedule?' ) ) {
		
			$.post( '/schedule/delete/', 
					{ job_id: $(this).attr('data-jobid') }, 
					function (result) {
						if ( result.is_success = false ) {
							$('#div_errorMessage')
								.text(result.message)
								.show();
						} else {
							window.location = '/schedule/';
						}
					}, 
					'json'
			);
		}
	});
	
});