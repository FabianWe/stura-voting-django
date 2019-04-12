# Copyright 2018 - 2019 Fabian Wenzelmann
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission

ADDITIONAL_KEYWORD = '__additional__'

ALL_PERMS = ['add', 'change', 'delete', 'view']

GROUPS = {'praesidium': {
            'voters revision': ALL_PERMS,
            'period': ALL_PERMS,
            'voting collection': ALL_PERMS,
            'voting group': ALL_PERMS,
            'median voting': ALL_PERMS,
            'schulze voting': ALL_PERMS,
            ADDITIONAL_KEYWORD: ['enter_collection_results'],
            },
         }

class Command(BaseCommand):
    help = 'Create groups commonly used in the tool and add permissions to them'

    def handle(self, *args, **options):
        print('Creating groups...')
        for group_name, perm_models in GROUPS.items():
            print('Group "%s"' % group_name)
            group, created = Group.objects.get_or_create(name=group_name)
            all_permissions = []
            if created:
                print('\tCreated new group "%s"' % group_name)
            additional = perm_models.pop(ADDITIONAL_KEYWORD, None)
            for p_model, perms in perm_models.items():
                for perm in perms:
                    name = "Can %s %s" % (perm, p_model)
                    print('   ... Adding permission "%s"' % name)
                    try:
                        perm_model = Permission.objects.get(name=name)
                        all_permissions.append(perm_model)
                    except Permission.DoesNotExist:
                        logging.warning('Permission "%s" not found' % name)
            # add additional ones if exist
            if additional:
                for c_name in additional:
                    print('   ... Adding permission "%s"' % c_name)
                    try:
                        perm_model = Permission.objects.get(codename=c_name)
                        all_permissions.append(perm_model)
                    except Permission.DoesNotExist:
                        logging.warning('Permission "%s" not found' % c_name)
            # add all collected permissions for this group, cast as tuple
            # to use in call to add
            perm_tuple = tuple(all_permissions)
            group.permissions.add(*perm_tuple)
