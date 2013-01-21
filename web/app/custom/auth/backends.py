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

from django.contrib.auth.backends import RemoteUserBackend


class HSNRemoteUserBackend(RemoteUserBackend):

    create_unknown_user = False

    def authenticate(self, **kwargs):
        if 'remote_user' in kwargs:
            return super(HSNRemoteUserBackend, self).authenticate(kwargs['remote_user'])
        else:
            return super(RemoteUserBackend, self).authenticate(kwargs['username'], kwargs['password'])
