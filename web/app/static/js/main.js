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

	// change color of 'Admin' link when on admin pages
	re_admin_page = /^\/admin\/.*/
	if ( re_admin_page.test(window.location.pathname)) {
		$('#admin_link').addClass('selectedMenuItem')	
	}

	// change color of 'Change password' link when on change password pages
	re_change_password_page = /^\/password.*/
	if ( re_change_password_page.test(window.location.pathname)) {
		$('#change_password_link').addClass('selectedMenuItem')	
	}
	
});