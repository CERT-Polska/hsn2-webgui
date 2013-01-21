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

from django.template import Node, NodeList, Template, Context, Variable
from django.template import TemplateSyntaxError, VariableDoesNotExist
from django.template import Library
from web.app.models import Schedule, Job

register = Library()

class IfJobRightsNode(Node):
    def __init__(self, job, user, nodelist_true, nodelist_false, negate):
        self.job, self.user = Variable(job), Variable(user)
        self.nodelist_true, self.nodelist_false = nodelist_true, nodelist_false
        self.negate = negate

    def __repr__(self):
        return "<IfJobRightsNode>"

    def render(self, context):
        try:
            job = self.job.resolve(context)
        except VariableDoesNotExist:
            job = None
        try:
            user = self.user.resolve(context)
        except VariableDoesNotExist:
            user = None

        owner = None
        if isinstance(job, Schedule):
            owner = job.created_by
        else:
            owner = job.owner

        if ( self.negate and owner is not user and not user.is_superuser and not job.is_public ) or \
            ( not self.negate and ( owner == user or user.is_superuser or job.is_public )):

            return self.nodelist_true.render(context)

        return self.nodelist_false.render(context)

def do_ifjobrights(parser, token, negate):
    bits = list(token.split_contents())
    if len(bits) != 3:
        raise TemplateSyntaxError, "%r takes two arguments" % bits[0]
    end_tag = 'end' + bits[0]
    nodelist_true = parser.parse(('else', end_tag))
    token = parser.next_token()
    if token.contents == 'else':
        nodelist_false = parser.parse((end_tag,))
        parser.delete_first_token()
    else:
        nodelist_false = NodeList()
    return IfJobRightsNode(bits[1], bits[2], nodelist_true, nodelist_false, negate)

@register.tag
def ifjobrights(parser, token):
    """
    Examples::

            {% ifjobrights job user %}
                    ...
            {% endifjobrights %}

            {% ifjobrights job user %}
                    ...
            {% else %}
                    ...
            {% endifnotjobrights %}
    """
    return do_ifjobrights(parser, token, False)

@register.tag
def ifnotjobrights(parser, token):
    return do_ifjobrights(parser, token, True)
