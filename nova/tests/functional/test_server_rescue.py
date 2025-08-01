# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from oslo_utils.fixture import uuidsentinel as uuids

from nova.tests import fixtures as nova_fixtures
from nova.tests.functional.api import client
from nova.tests.functional import integrated_helpers


class BFVRescue(integrated_helpers.ProviderUsageBaseTestCase):
    """Base class for various boot from volume rescue tests."""

    def setUp(self):
        super(BFVRescue, self).setUp()
        self.useFixture(nova_fixtures.CinderFixture(self))
        self._start_compute(host='host1')

    def _create_image(self, metadata=None):
        image = {
            'id': uuids.stable_rescue_image,
            'name': 'fake-image-rescue-property',
            'created_at': datetime.datetime(2011, 1, 1, 1, 2, 3),
            'updated_at': datetime.datetime(2011, 1, 1, 1, 2, 3),
            'deleted_at': None,
            'deleted': False,
            'status': 'active',
            'is_public': False,
            'container_format': 'raw',
            'disk_format': 'raw',
            'size': 25165824,
            'min_ram': 0,
            'min_disk': 0,
            'protected': False,
            'visibility': 'public',
            'tags': ['tag1', 'tag2'],
            'properties': {
                'kernel_id': 'nokernel',
                'ramdisk_id': 'nokernel',
                'hw_rescue_device': 'disk',
                'hw_rescue_bus': 'scsi',
            },
        }
        if metadata:
            image['properties'].update(metadata)
        return self.glance.create(None, image)

    def _create_bfv_server(self, metadata=None):
        image = self._create_image(metadata=metadata)
        server_request = self._build_server(networks=[])
        server_request.pop('imageRef')
        server_request['block_device_mapping_v2'] = [{
            'boot_index': 0,
            'uuid': nova_fixtures.CinderFixture.IMAGE_BACKED_VOL,
            'source_type': 'volume',
            'destination_type': 'volume'}]
        server = self.api.post_server({'server': server_request})
        self._wait_for_state_change(server, 'ACTIVE')
        return server, image


class DisallowBFVRescuev286(BFVRescue):
    """Asserts that BFV rescue requests fail prior to microversion 2.87.
    """
    compute_driver = 'fake.MediumFakeDriver'
    microversion = '2.86'

    def test_bfv_rescue_not_supported(self):
        server, image = self._create_bfv_server()
        ex = self.assertRaises(client.OpenStackApiException,
            self.api.post_server_action, server['id'], {'rescue': {
            'rescue_image_ref': image['id']}})
        self.assertEqual(400, ex.response.status_code)
        self.assertIn('Cannot rescue a volume-backed instance',
                      ex.response.text)


class DisallowBFVRescuev286WithTrait(BFVRescue):
    """Asserts that BFV rescue requests fail prior to microversion 2.87 even
       when the required COMPUTE_RESCUE_BFV trait is reported by the compute.
    """
    compute_driver = 'fake.RescueBFVDriver'
    microversion = '2.86'

    def test_bfv_rescue_not_supported(self):
        server, image = self._create_bfv_server()
        ex = self.assertRaises(client.OpenStackApiException,
            self.api.post_server_action, server['id'], {'rescue': {
            'rescue_image_ref': image['id']}})
        self.assertEqual(400, ex.response.status_code)
        self.assertIn('Cannot rescue a volume-backed instance',
                      ex.response.text)


class DisallowBFVRescuev287WithoutTrait(BFVRescue):
    """Asserts that BFV rescue requests fail with microversion 2.87 (or later)
    when the required COMPUTE_RESCUE_BFV trait is not reported by the compute.
    """
    compute_driver = 'fake.MediumFakeDriver'
    microversion = '2.87'

    def test_bfv_rescue_not_supported(self):
        server, image = self._create_bfv_server()
        ex = self.assertRaises(client.OpenStackApiException,
            self.api.post_server_action, server['id'], {'rescue': {
            'rescue_image_ref': image['id']}})
        self.assertEqual(400, ex.response.status_code)
        self.assertIn('Host unable to rescue a volume-backed instance',
                      ex.response.text)


class AllowBFVRescuev287WithTrait(BFVRescue):
    """Asserts that BFV rescue requests pass with microversion 2.87 (or later)
    when the required COMPUTE_RESCUE_BFV trait is reported by the compute.
    """
    compute_driver = 'fake.RescueBFVDriver'
    microversion = '2.87'

    def test_bfv_rescue_supported(self):
        server, image = self._create_bfv_server()
        self.api.post_server_action(server['id'], {'rescue': {
            'rescue_image_ref': image['id']}})
        self._wait_for_state_change(server, 'RESCUE')


class DisallowBFVRescuev287WithoutRescueImageProperties(BFVRescue):
    """Asserts that BFV rescue requests fail with microversion 2.87 (or later)
    when the required hw_rescue_device and hw_rescue_bus image properties
    are not set on the image.
    """
    compute_driver = 'fake.MediumFakeDriver'
    microversion = '2.87'

    def test_bfv_rescue_failed(self):
        server, image = self._create_bfv_server()
        # try rescue without hw_rescue_device and hw_rescue_bus properties set
        ex = self.assertRaises(client.OpenStackApiException,
            self.api.post_server_action, server['id'], {'rescue': {
            'rescue_image_ref': '155d900f-4e14-4e4c-a73d-069cbf4541e6'}})
        self.assertEqual(400, ex.response.status_code)
        self.assertIn('Cannot rescue a volume-backed instance',
                      ex.response.text)


class AllowBFVRescuev287WithRescueImageProperties(BFVRescue):
    """Asserts that BFV rescue requests pass with microversion 2.87 (or later)
    when the required hw_rescue_device and hw_rescue_bus image properties
    are set on the image.
    """
    compute_driver = 'fake.RescueBFVDriver'
    microversion = '2.87'

    def test_bfv_rescue_done(self):
        server, image = self._create_bfv_server()
        self.api.post_server_action(server['id'], {'rescue': {
            'rescue_image_ref': image['id']}})
        self._wait_for_state_change(server, 'RESCUE')
