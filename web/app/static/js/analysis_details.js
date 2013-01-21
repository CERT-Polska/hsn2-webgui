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

	var oTable = $('#tbl_urls').dataTable( {
		'sScrollY': '20em',
	    'bPaginate': false,
	    'sDom': '<"toolbar">frtip',
	    "oLanguage": {
        	"sSearch": "Filter: "
      	}	    	    
	});	
	
	// fetch analysis data
	$('.analyzedUrl').click( function () {
		var node = $(this).attr('id');
		var url = $(this).text();
		$('#analyzedUrlData').html('<span class="italic">getting analyzer data...</span>');
				
		$.post( '/getanalyzerdetails/', 
				{ node_id: node }, 
				function ( result ) {
					if ( result.is_success ) {
						$('#analyzedUrlData').html('<span class="titleSmall">' + url + '</span>' + result.details);
						$('.dataValueText').each( function (index) {
							if ( $(this).text().match(/^(UNCLASSIFIED|BENIGN|SUSPICIOUS|OBFUSCATED|MALICIOUS)$/i) ) {
								$(this).addClass( $(this).text().toLowerCase() + ' bold' );
							}
						});
						$('.dataListTitle').siblings().css({'display': 'none'})
						$('.dataListTitle').siblings('ul:first').show();
						
						$('.listFolding:first').html('&minus;');
					} else {
						alert(result.message)
					}
				}, 'json' );
	});

	// expand/collapse list items
	$('#analyzedUrlData').on( 'click', '.dataListTitle', function () {
		$(this).siblings('ul').slideToggle('fast');
		
		if ( $(this).children('.listFolding').text() == '+' ) {
			$(this).children('.listFolding').html('&minus;');
		} else {
			$(this).children('.listFolding').html('+');
		}
	});

	// pretty print code sections when clicking on it
	$('#analyzedUrlData').on( 'click', '.dataValueTextPretty', function () {
		$(this).html(prettyPrintOne($(this).html()));
		$(this).removeClass('pointer');
	});
	
	// expand all
	$('#expandAll').click( function () {
		$('.dataListTitle').siblings('ul').show();
		$('.dataListTitle').children('.listFolding').html('&minus;');
	});

	// collapse all
	$('#collapseAll').click( function () {
		$('.dataListTitle').siblings('ul').hide();
		$('.dataListTitle').children('.listFolding').html('+');
	});	
});