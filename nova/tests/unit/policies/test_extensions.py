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

from nova.api.openstack.compute import extension_info
from nova.policies import extensions as policies
from nova.tests.unit.api.openstack import fakes
from nova.tests.unit.policies import base


class ExtensionsPolicyTest(base.BasePolicyTest):
    """Test Extensions APIs policies with all possible context.
    This class defines the set of context with different roles
    which are allowed and not allowed to pass the policy checks.
    With those set of context, it will call the API operation and
    verify the expected behaviour.
    """

    def setUp(self):
        super(ExtensionsPolicyTest, self).setUp()
        self.controller = extension_info.ExtensionInfoController()
        self.req = fakes.HTTPRequest.blank('')

        # Check that everyone is able to get extension info.
        self.everyone_authorized_contexts = [
            self.legacy_admin_context, self.system_admin_context,
            self.project_admin_context, self.project_manager_context,
            self.project_member_context, self.project_reader_context,
            self.project_foo_context,
            self.other_project_reader_context,
            self.system_member_context, self.system_reader_context,
            self.system_foo_context,
            self.other_project_manager_context,
            self.other_project_member_context
        ]
        self.everyone_unauthorized_contexts = []

    def test_list_extensions_policy(self):
        rule_name = policies.BASE_POLICY_NAME
        self.common_policy_check(self.everyone_authorized_contexts,
                                 self.everyone_unauthorized_contexts,
                                 rule_name,
                                 self.controller.index,
                                 self.req)

    def test_show_extensions_policy(self):
        rule_name = policies.BASE_POLICY_NAME
        self.common_policy_check(self.everyone_authorized_contexts,
                                 self.everyone_unauthorized_contexts,
                                 rule_name,
                                 self.controller.show,
                                 self.req, 'os-volumes')


class ExtensionsScopeTypePolicyTest(ExtensionsPolicyTest):
    """Test Extensions APIs policies with system scope enabled.
    This class set the nova.conf [oslo_policy] enforce_scope to True
    so that we can switch on the scope checking on oslo policy side.
    It defines the set of context with scoped token
    which are allowed and not allowed to pass the policy checks.
    With those set of context, it will run the API operation and
    verify the expected behaviour.
    """

    def setUp(self):
        super(ExtensionsScopeTypePolicyTest, self).setUp()
        self.flags(enforce_scope=True, group="oslo_policy")
        self.everyone_authorized_contexts = [
            self.legacy_admin_context,
            self.project_admin_context, self.project_manager_context,
            self.project_member_context, self.project_reader_context,
            self.project_foo_context,
            self.other_project_manager_context,
            self.other_project_reader_context,
            self.other_project_member_context
        ]
        self.everyone_unauthorized_contexts = [
            self.system_admin_context, self.system_member_context,
            self.system_reader_context, self.system_foo_context]


class ExtensionsNoLegacyPolicyTest(ExtensionsScopeTypePolicyTest):
    """Test Extensions APIs policies with system scope enabled,
    and no more deprecated rules.
    """
    without_deprecated_rules = True
