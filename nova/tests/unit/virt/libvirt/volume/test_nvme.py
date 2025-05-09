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

from unittest import mock

from nova.tests.unit.virt.libvirt.volume import test_volume
from nova.virt.libvirt.volume import nvme

from os_brick import initiator


class LibvirtNVMEVolumeDriverTestCase(test_volume.LibvirtVolumeBaseTestCase):

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('nova.utils.get_root_helper')
    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory')
    def test_libvirt_nvme_driver(self, mock_factory, mock_helper, exists):
        self.flags(num_nvme_discover_tries=3, group='libvirt')
        mock_helper.return_value = 'sudo'

        nvme.LibvirtNVMEVolumeDriver(self.fake_host)
        mock_factory.assert_called_once_with(
            initiator.NVME, 'sudo', use_multipath=False,
            device_scan_attempts=3, enforce_multipath=False)

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('nova.utils.get_root_helper')
    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory')
    def test_libvirt_nvme_driver_multipath(self, mock_factory, mock_helper,
                                           exists):
        self.flags(num_nvme_discover_tries=3, volume_use_multipath=True,
                   group='libvirt')
        mock_helper.return_value = 'sudo'

        nvme.LibvirtNVMEVolumeDriver(self.fake_host)
        mock_factory.assert_called_once_with(
            initiator.NVME, 'sudo', use_multipath=True,
            device_scan_attempts=3, enforce_multipath=False)

    @mock.patch('os.path.exists', return_value=True)
    @mock.patch('nova.utils.get_root_helper')
    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory')
    def test_libvirt_nvme_driver_multipath_enforced(self, mock_factory,
                                                    mock_helper, exists):
        self.flags(num_nvme_discover_tries=3, volume_use_multipath=True,
                   volume_enforce_multipath=True, group='libvirt')
        mock_helper.return_value = 'sudo'

        nvme.LibvirtNVMEVolumeDriver(self.fake_host)
        mock_factory.assert_called_once_with(
            initiator.NVME, 'sudo', use_multipath=True,
            device_scan_attempts=3, enforce_multipath=True)

    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory',
        new=mock.Mock(return_value=mock.Mock()))
    def test_libvirt_nvme_driver_connect(self):
        nvme_driver = nvme.LibvirtNVMEVolumeDriver(self.fake_host)
        config = {'server_ip': '127.0.0.1', 'server_port': 9898}
        disk_info = {
            'id': '1234567',
            'name': 'aNVMEVolume',
            'conf': config}
        connection_info = {'data': disk_info}
        nvme_driver.connector.connect_volume.return_value = (
            {'path': '/dev/dms1234567'})

        nvme_driver.connect_volume(connection_info, None)

        nvme_driver.connector.connect_volume.assert_called_once_with(
            connection_info['data'])
        self.assertEqual(
            '/dev/dms1234567', connection_info['data']['device_path'])

    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory',
        new=mock.Mock(return_value=mock.Mock()))
    def test_libvirt_nvme_driver_disconnect(self):
        nvme_driver = nvme.LibvirtNVMEVolumeDriver(self.connr)
        disk_info = {
            'path': '/dev/dms1234567', 'name': 'aNVMEVolume',
                     'type': 'raw', 'dev': 'vda1', 'bus': 'pci0',
                     'device_path': '/dev/dms123456'}
        connection_info = {'data': disk_info}
        nvme_driver.disconnect_volume(connection_info, None)
        nvme_driver.connector.disconnect_volume.assert_called_once_with(
            disk_info, None, force=False)

        # Verify force=True
        nvme_driver.connector.disconnect_volume.reset_mock()
        nvme_driver.disconnect_volume(connection_info, None, force=True)
        nvme_driver.connector.disconnect_volume.assert_called_once_with(
            disk_info, None, force=True)

    @mock.patch('os_brick.initiator.connector.InitiatorConnector.factory',
        new=mock.Mock(return_value=mock.Mock()))
    def test_libvirt_nvme_driver_get_config(self):
        nvme_driver = nvme.LibvirtNVMEVolumeDriver(self.fake_host)
        device_path = '/dev/fake-dev'
        connection_info = {'data': {'device_path': device_path}}

        conf = nvme_driver.get_config(connection_info, self.disk_info)
        tree = conf.format_dom()

        self.assertEqual('block', tree.get('type'))
        self.assertEqual(device_path, tree.find('./source').get('dev'))
        self.assertEqual('raw', tree.find('./driver').get('type'))
