#   Copyright 2013 OpenStack Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.


from oslo_log import log as logging
from oslo_utils import strutils
from webob import exc

from nova.api.openstack import api_version_request
from nova.api.openstack import common
from nova.api.openstack.compute.schemas import evacuate
from nova.api.openstack import wsgi
from nova.api import validation
from nova.compute import api as compute
from nova.compute import vm_states
import nova.conf
from nova import exception
from nova.i18n import _
from nova import objects
from nova.policies import evacuate as evac_policies
from nova import utils

CONF = nova.conf.CONF

LOG = logging.getLogger(__name__)

MIN_VER_NOVA_COMPUTE_EVACUATE_STOPPED = 62


@validation.validated
class EvacuateController(wsgi.Controller):
    def __init__(self):
        super(EvacuateController, self).__init__()
        self.compute_api = compute.API()
        self.host_api = compute.HostAPI()

    def _get_on_shared_storage(self, req, evacuate_body):
        if api_version_request.is_supported(req, '2.14'):
            return None
        else:
            return strutils.bool_from_string(evacuate_body["onSharedStorage"])

    def _get_password(self, req, evacuate_body, on_shared_storage):
        password = None
        if 'adminPass' in evacuate_body:
            # check that if requested to evacuate server on shared storage
            # password not specified
            if on_shared_storage:
                msg = _("admin password can't be changed on existing disk")
                raise exc.HTTPBadRequest(explanation=msg)

            password = evacuate_body['adminPass']
        elif not on_shared_storage:
            password = utils.generate_password()

        return password

    def _get_password_v214(self, req, evacuate_body):
        if 'adminPass' in evacuate_body:
            password = evacuate_body['adminPass']
        else:
            password = utils.generate_password()

        return password

    # TODO(eliqiao): Should be responding here with 202 Accept
    # because evacuate is an async call, but keep to 200 for
    # backwards compatibility reasons.
    @wsgi.expected_errors((400, 403, 404, 409))
    @wsgi.action('evacuate')
    @validation.schema(evacuate.evacuate, "2.0", "2.13")
    @validation.schema(evacuate.evacuate_v214, "2.14", "2.28")
    @validation.schema(evacuate.evacuate_v229, "2.29", "2.67")
    @validation.schema(evacuate.evacuate_v268, "2.68", "2.94")
    @validation.schema(evacuate.evacuate_v295, "2.95")
    @validation.response_body_schema(
        evacuate.evacuate_response, "2.0", "2.13"
    )
    @validation.response_body_schema(evacuate.evacuate_response_v214, "2.14")
    def _evacuate(self, req, id, body):
        """Permit admins to evacuate a server from a failed host
        to a new one.
        """
        context = req.environ["nova.context"]
        instance = common.get_instance(self.compute_api, context, id,
                                       expected_attrs=['trusted_certs',
                                                       'pci_requests',
                                                       'pci_devices',
                                                       'resources',
                                                       'migration_context'])

        context.can(evac_policies.BASE_POLICY_NAME,
                    target={'user_id': instance.user_id,
                            'project_id': instance.project_id})

        evacuate_body = body["evacuate"]
        host = evacuate_body.get("host")
        force = None

        target_state = None
        if api_version_request.is_supported(req, '2.95'):
            min_ver = objects.service.get_minimum_version_all_cells(
                context, ['nova-compute'])
            if min_ver < MIN_VER_NOVA_COMPUTE_EVACUATE_STOPPED:
                raise exception.NotSupportedComputeForEvacuateV295(
                    {'currently': min_ver,
                     'expected': MIN_VER_NOVA_COMPUTE_EVACUATE_STOPPED})
            # Starts to 2.95 any evacuated instances will be stopped at
            # destination. Previously an active or stopped instance would have
            # kept its state.
            target_state = vm_states.STOPPED

        on_shared_storage = self._get_on_shared_storage(req, evacuate_body)

        if api_version_request.is_supported(req, '2.29'):
            force = body["evacuate"].get("force", False)
            force = strutils.bool_from_string(force, strict=True)
            if force is True and not host:
                message = _("Can't force to a non-provided destination")
                raise exc.HTTPBadRequest(explanation=message)
        if api_version_request.is_supported(req, '2.14'):
            password = self._get_password_v214(req, evacuate_body)
        else:
            password = self._get_password(req, evacuate_body,
                                          on_shared_storage)

        if host is not None:
            try:
                self.host_api.service_get_by_compute_host(context, host)
            except (exception.ComputeHostNotFound,
                    exception.HostMappingNotFound):
                msg = _("Compute host %s not found.") % host
                raise exc.HTTPNotFound(explanation=msg)

        if instance.host == host:
            msg = _("The target host can't be the same one.")
            raise exc.HTTPBadRequest(explanation=msg)

        try:
            self.compute_api.evacuate(context, instance, host,
                                      on_shared_storage, password, force,
                                      target_state)
        except exception.InstanceInvalidState as state_error:
            common.raise_http_conflict_for_instance_invalid_state(
                state_error, 'evacuate', id)
        except (
            exception.ComputeServiceInUse,
            exception.ForbiddenPortsWithAccelerator,
            exception.ExtendedResourceRequestOldCompute,
        ) as e:
            raise exc.HTTPBadRequest(explanation=e.format_message())
        except exception.UnsupportedRPCVersion as e:
            raise exc.HTTPConflict(explanation=e.format_message())
        except (
            exception.ForbiddenSharesNotSupported,
            exception.ForbiddenWithShare,
        ) as e:
            raise exc.HTTPConflict(explanation=e.format_message())

        if (
            not api_version_request.is_supported(req, '2.14') and
            CONF.api.enable_instance_password
        ):
            return {'adminPass': password}
        else:
            return None
