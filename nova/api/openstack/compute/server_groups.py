# Copyright (c) 2014 Cisco Systems, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""The Server Group API Extension."""

import collections

from oslo_log import log as logging
import webob
from webob import exc

from nova.api.openstack import api_version_request
from nova.api.openstack import common
from nova.api.openstack.compute.schemas import server_groups as schema
from nova.api.openstack import wsgi
from nova.api import validation
import nova.conf
from nova import context as nova_context
import nova.exception
from nova.i18n import _
from nova.limit import local as local_limit
from nova import objects
from nova.objects import service
from nova.policies import server_groups as sg_policies

LOG = logging.getLogger(__name__)

CONF = nova.conf.CONF


def _get_not_deleted(context, uuids):
    mappings = objects.InstanceMappingList.get_by_instance_uuids(
        context, uuids)
    inst_by_cell = collections.defaultdict(list)
    cell_mappings = {}
    found_inst_uuids = []

    # Get a master list of cell mappings, and a list of instance
    # uuids organized by cell
    for im in mappings:
        if not im.cell_mapping:
            # Not scheduled yet, so just throw it in the final list
            # and move on
            found_inst_uuids.append(im.instance_uuid)
            continue
        if im.cell_mapping.uuid not in cell_mappings:
            cell_mappings[im.cell_mapping.uuid] = im.cell_mapping
        inst_by_cell[im.cell_mapping.uuid].append(im.instance_uuid)

    # Query each cell for the instances that are inside, building
    # a list of non-deleted instance uuids.
    for cell_uuid, cell_mapping in cell_mappings.items():
        inst_uuids = inst_by_cell[cell_uuid]
        LOG.debug('Querying cell %(cell)s for %(num)i instances',
                  {'cell': cell_mapping.identity, 'num': len(inst_uuids)})
        filters = {'uuid': inst_uuids, 'deleted': False}
        with nova_context.target_cell(context, cell_mapping) as ctx:
            found_inst_uuids.extend([
                inst.uuid for inst in objects.InstanceList.get_by_filters(
                    ctx, filters=filters)])

    return found_inst_uuids


def _should_enable_custom_max_server_rules(context, rules):
    if rules and int(rules.get('max_server_per_host', 1)) > 1:
        minver = service.get_minimum_version_all_cells(
            context, ['nova-compute'])
        if minver < 33:
            return False
    return True


@validation.validated
class ServerGroupController(wsgi.Controller):
    """The Server group API controller for the OpenStack API."""

    def _format_server_group(self, context, group, req):
        # the id field has its value as the uuid of the server group
        # There is no 'uuid' key in server_group seen by clients.
        # In addition, clients see policies as a ["policy-name"] list;
        # and they see members as a ["server-id"] list.
        server_group = {}
        server_group['id'] = group.uuid
        server_group['name'] = group.name
        if api_version_request.is_supported(req, '2.64'):
            server_group['policy'] = group.policy
            server_group['rules'] = group.rules
        else:
            server_group['policies'] = group.policies or []
            # NOTE(yikun): Before v2.64, a empty metadata is exposed to the
            # user, and it is removed since v2.64.
            server_group['metadata'] = {}
        members = []
        if group.members:
            # Display the instances that are not deleted.
            members = _get_not_deleted(context, group.members)
        server_group['members'] = members
        # Add project id information to the response data for
        # API version v2.13
        if api_version_request.is_supported(req, "2.13"):
            server_group['project_id'] = group.project_id
            server_group['user_id'] = group.user_id
        return server_group

    @wsgi.expected_errors(404)
    @validation.query_schema(schema.show_query)
    @validation.response_body_schema(schema.show_response, '2.1', '2.12')
    @validation.response_body_schema(schema.show_response_v213, '2.13', '2.14')
    @validation.response_body_schema(schema.show_response_v215, '2.15', '2.63')
    @validation.response_body_schema(schema.show_response_v264, '2.64')
    def show(self, req, id):
        """Return data about the given server group."""
        context = req.environ['nova.context']
        try:
            sg = objects.InstanceGroup.get_by_uuid(context, id)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        context.can(sg_policies.POLICY_ROOT % 'show',
                    target={'project_id': sg.project_id})
        return {'server_group': self._format_server_group(context, sg, req)}

    @wsgi.response(204)
    @wsgi.expected_errors(404)
    @validation.response_body_schema(schema.delete_response)
    def delete(self, req, id):
        """Delete a server group."""
        context = req.environ['nova.context']
        try:
            sg = objects.InstanceGroup.get_by_uuid(context, id)
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())
        context.can(sg_policies.POLICY_ROOT % 'delete',
                    target={'project_id': sg.project_id})
        try:
            sg.destroy()
        except nova.exception.InstanceGroupNotFound as e:
            raise webob.exc.HTTPNotFound(explanation=e.format_message())

    @wsgi.expected_errors(())
    @validation.query_schema(schema.index_query, '2.0', '2.74')
    @validation.query_schema(schema.index_query_v275, '2.75')
    @validation.response_body_schema(schema.index_response, '2.1', '2.12')
    @validation.response_body_schema(schema.index_response_v213, '2.13', '2.14')  # noqa: E501
    @validation.response_body_schema(schema.index_response_v215, '2.15', '2.63')  # noqa: E501
    @validation.response_body_schema(schema.index_response_v264, '2.64')
    def index(self, req):
        """Returns a list of server groups."""
        context = req.environ['nova.context']
        project_id = context.project_id
        # NOTE(gmann): Using context's project_id as target here so
        # that when we remove the default target from policy class,
        # it does not fail if user requesting operation on for their
        # own server group.
        context.can(sg_policies.POLICY_ROOT % 'index',
                    target={'project_id': project_id})
        if 'all_projects' in req.GET and context.is_admin:
            # TODO(gmann): Remove the is_admin check in the above condition
            # so that the below policy can raise error if not allowed.
            # In existing behavior, if non-admin users requesting
            # all projects server groups they do not get error instead
            # get their own server groups. Once we switch to policy
            # new defaults completely then we can remove the above check.
            # Until then, let's keep the old behaviour.
            context.can(sg_policies.POLICY_ROOT % 'index:all_projects',
                        target={'project_id': project_id})
            sgs = objects.InstanceGroupList.get_all(context)
        else:
            sgs = objects.InstanceGroupList.get_by_project_id(
                    context, project_id)
        limited_list = common.limited(sgs.objects, req)
        result = [self._format_server_group(context, group, req)
                  for group in limited_list]
        return {'server_groups': result}

    @wsgi.api_version("2.1")
    @wsgi.expected_errors((400, 403, 409))
    @validation.schema(schema.create, "2.0", "2.14")
    @validation.schema(schema.create_v215, "2.15", "2.63")
    @validation.schema(schema.create_v264, "2.64")
    @validation.response_body_schema(schema.create_response, '2.1', '2.12')
    @validation.response_body_schema(schema.create_response_v213, '2.13', '2.14')  # noqa: E501
    @validation.response_body_schema(schema.create_response_v215, '2.15', '2.63')  # noqa: E501
    @validation.response_body_schema(schema.create_response_v264, '2.64')
    def create(self, req, body):
        """Creates a new server group."""
        context = req.environ['nova.context']
        project_id = context.project_id
        context.can(sg_policies.POLICY_ROOT % 'create',
                    target={'project_id': project_id})
        try:
            objects.Quotas.check_deltas(context, {'server_groups': 1},
                                        project_id, context.user_id)
            local_limit.enforce_db_limit(context, local_limit.SERVER_GROUPS,
                                         entity_scope=project_id, delta=1)
        except nova.exception.ServerGroupLimitExceeded as e:
            raise exc.HTTPForbidden(explanation=str(e))
        except nova.exception.OverQuota:
            msg = _("Quota exceeded, too many server groups.")
            raise exc.HTTPForbidden(explanation=msg)

        vals = body['server_group']

        if api_version_request.is_supported(req, "2.64"):
            policy = vals['policy']
            rules = vals.get('rules', {})
            if policy != 'anti-affinity' and rules:
                msg = _("Only anti-affinity policy supports rules.")
                raise exc.HTTPBadRequest(explanation=msg)
            # NOTE(yikun): This should be removed in Stein version.
            if not _should_enable_custom_max_server_rules(context, rules):
                msg = _("Creating an anti-affinity group with rule "
                        "max_server_per_host > 1 is not yet supported.")
                raise exc.HTTPConflict(explanation=msg)
            sg = objects.InstanceGroup(context, policy=policy,
                                       rules=rules)
        else:
            policies = vals.get('policies')
            sg = objects.InstanceGroup(context, policy=policies[0])
        try:
            sg.name = vals.get('name')
            sg.project_id = project_id
            sg.user_id = context.user_id
            sg.create()
        except ValueError as e:
            raise exc.HTTPBadRequest(explanation=e)

        # NOTE(melwitt): We recheck the quota after creating the object to
        # prevent users from allocating more resources than their allowed quota
        # in the event of a race. This is configurable because it can be
        # expensive if strict quota limits are not required in a deployment.
        if CONF.quota.recheck_quota:
            try:
                objects.Quotas.check_deltas(context, {'server_groups': 0},
                                            project_id,
                                            context.user_id)
                # TODO(johngarbutt): decide if we need this recheck
                # The quota rechecking of limits is really just to protect
                # against denial of service attacks that aim to fill up the
                # database. Its usefulness could be debated.
                local_limit.enforce_db_limit(context,
                                             local_limit.SERVER_GROUPS,
                                             project_id, delta=0)
            except nova.exception.ServerGroupLimitExceeded as e:
                sg.destroy()
                raise exc.HTTPForbidden(explanation=str(e))
            except nova.exception.OverQuota:
                sg.destroy()
                msg = _("Quota exceeded, too many server groups.")
                raise exc.HTTPForbidden(explanation=msg)

        return {'server_group': self._format_server_group(context, sg, req)}
