# Copyright 2011 OpenStack Foundation
# Copyright 2013 IBM Corp.
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

from unittest import mock

from oslo_utils.fixture import uuidsentinel as uuids
from oslo_utils import timeutils
import webob

from nova.api.openstack import common
from nova.api.openstack.compute import create_backup
from nova.compute import api
from nova.compute import utils as compute_utils
from nova import exception
from nova import test
from nova.tests.unit.api.openstack.compute import admin_only_action_common
from nova.tests.unit.api.openstack import fakes
from nova.tests.unit import fake_instance


class CreateBackupTestsV21(admin_only_action_common.CommonMixin,
                        test.NoDBTestCase):
    create_backup = create_backup
    controller_name = 'CreateBackupController'
    validation_error = exception.ValidationError

    def setUp(self):
        super(CreateBackupTestsV21, self).setUp()
        self.controller = getattr(self.create_backup, self.controller_name)()
        self.compute_api = self.controller.compute_api

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup')
    def test_create_backup_with_metadata(self, mock_backup, mock_check_image):
        metadata = {'123': 'asdf'}
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
                'metadata': metadata,
            },
        }

        image = dict(id=uuids.image_id, status='ACTIVE', name='Backup 1',
                     properties=metadata)

        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        mock_backup.return_value = image

        res = self.controller._create_backup(self.req, instance.uuid,
                                             body=body)

        mock_check_image.assert_called_once_with(self.context, metadata)
        mock_backup.assert_called_once_with(self.context, instance, 'Backup 1',
                                              'daily', 1,
                                              extra_properties=metadata)

        self.assertEqual(202, res.status_int)
        self.assertIn(uuids.image_id, res.headers['Location'])

    def test_create_backup_no_name(self):
        # Name is required for backups.
        body = {
            'createBackup': {
                'backup_type': 'daily',
                'rotation': 1,
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_name_with_leading_trailing_spaces(self):
        body = {
            'createBackup': {
                'name': '  test  ',
                'backup_type': 'daily',
                'rotation': 1,
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup')
    def test_create_backup_name_with_leading_trailing_spaces_compat_mode(
            self, mock_backup, mock_check_image):
        body = {
            'createBackup': {
                'name': '  test  ',
                'backup_type': 'daily',
                'rotation': 1,
            },
        }
        image = dict(id=uuids.image_id, status='ACTIVE', name='Backup 1',
                     properties={})
        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        mock_backup.return_value = image

        self.req.set_legacy_v2()
        self.controller._create_backup(self.req, instance.uuid,
                                       body=body)

        mock_check_image.assert_called_once_with(self.context, {})
        mock_backup.assert_called_once_with(self.context, instance, 'test',
                                              'daily', 1,
                                              extra_properties={})

    def test_create_backup_no_rotation(self):
        # Rotation is required for backup requests.
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_negative_rotation(self):
        """Rotation must be greater than or equal to zero
        for backup requests
        """
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': -1,
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_negative_rotation_with_string_number(self):
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': '-1',
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_rotation_with_empty_string(self):
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': '',
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_no_backup_type(self):
        # Backup Type (daily or weekly) is required for backup requests.
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'rotation': 1,
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_non_dict_metadata(self):
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
                'metadata': 'non_dict',
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    def test_create_backup_bad_entity(self):
        body = {'createBackup': 'go'}
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup')
    def test_create_backup_rotation_is_zero(self, mock_backup,
                                         mock_check_image):
        # The happy path for creating backups if rotation is zero.
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 0,
            },
        }

        image = dict(id=uuids.image_id, status='ACTIVE', name='Backup 1',
                     properties={})
        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        mock_backup.return_value = image

        res = self.controller._create_backup(self.req, instance.uuid,
                                             body=body)

        mock_check_image.assert_called_once_with(self.context, {})
        mock_backup.assert_called_once_with(self.context, instance, 'Backup 1',
                                              'daily', 0,
                                              extra_properties={})
        self.assertEqual(202, res.status_int)
        self.assertNotIn('Location', res.headers)

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup')
    def test_create_backup_rotation_is_positive(self, mock_backup,
                                                mock_check_image):
        # The happy path for creating backups if rotation is positive.
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
            },
        }

        image = dict(id=uuids.image_id, status='ACTIVE', name='Backup 1',
                     properties={})
        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        mock_backup.return_value = image

        res = self.controller._create_backup(self.req, instance.uuid,
                                             body=body)

        mock_check_image.assert_called_once_with(self.context, {})
        mock_backup.assert_called_once_with(self.context, instance, 'Backup 1',
                                              'daily', 1,
                                              extra_properties={})

        self.assertEqual(202, res.status_int)
        self.assertIn(uuids.image_id, res.headers['Location'])

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup')
    def test_create_backup_rotation_is_string_number(
                                self, mock_backup, mock_check_image):
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': '1',
            },
        }

        image = dict(id=uuids.image_id, status='ACTIVE', name='Backup 1',
                     properties={})
        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        mock_backup.return_value = image

        res = self.controller._create_backup(self.req, instance['uuid'],
                                             body=body)

        mock_check_image.assert_called_once_with(self.context, {})
        mock_backup.assert_called_once_with(self.context, instance, 'Backup 1',
                                              'daily', 1,
                                              extra_properties={})
        self.assertEqual(202, res.status_int)
        self.assertIn(uuids.image_id, res.headers['Location'])

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup', return_value=dict(
        id=uuids.image_id, status='ACTIVE', name='Backup 1', properties={}))
    def test_create_backup_v2_45(self, mock_backup, mock_check_image):
        """Tests the 2.45 microversion to ensure the Location header is not
        in the response.
        """
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': '1',
            },
        }
        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        req = fakes.HTTPRequest.blank('', version='2.45')
        res = self.controller._create_backup(req, instance['uuid'], body=body)
        self.assertIsInstance(res, dict)
        self.assertEqual(uuids.image_id, res['image_id'])

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(api.API, 'backup')
    def test_create_backup_raises_conflict_on_invalid_state(self,
                                   mock_backup, mock_check_image):
        body_map = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
            },
        }
        instance = fake_instance.fake_instance_obj(self.context)
        self.mock_get.return_value = instance
        mock_backup.side_effect = exception.InstanceInvalidState(
                            attr='vm_state', instance_uuid=instance.uuid,
                            state='foo', method='backup')

        ex = self.assertRaises(webob.exc.HTTPConflict,
                          self.controller._create_backup,
                          self.req, instance.uuid,
                          body=body_map)
        self.assertIn("Cannot 'createBackup' instance %(id)s"
                      % {'id': instance.uuid}, ex.explanation)

    def test_create_backup_with_non_existed_instance(self):
        body_map = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
            },
        }
        uuid = fakes.FAKE_UUID
        self.mock_get.side_effect = exception.InstanceNotFound(
                                            instance_id=uuid)
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller._create_backup,
                          self.req, uuid, body=body_map)

    def test_create_backup_with_invalid_create_backup(self):
        body = {
            'createBackupup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
            },
        }
        self.assertRaises(self.validation_error,
                          self.controller._create_backup,
                          self.req, fakes.FAKE_UUID, body=body)

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(compute_utils, 'is_volume_backed_instance',
                       return_value=True)
    def test_backup_volume_backed_instance(self, mock_is_volume_backed,
                                           mock_check_image):
        body = {
            'createBackup': {
                'name': 'BackupMe',
                'backup_type': 'daily',
                'rotation': 3
            },
        }

        updates = {'vm_state': 'active',
                   'task_state': None,
                   'launched_at': timeutils.utcnow()}
        instance = fake_instance.fake_instance_obj(self.context, **updates)
        instance.image_ref = None
        self.mock_get.return_value = instance

        ex = self.assertRaises(webob.exc.HTTPBadRequest,
                               self.controller._create_backup,
                               self.req, instance['uuid'], body=body)
        mock_check_image.assert_called_once_with(self.context, {})
        mock_is_volume_backed.assert_called_once_with(self.context, instance)
        self.assertIn('Backup is not supported for volume-backed instances',
                      str(ex))


class CreateBackupTestsV239(test.NoDBTestCase):

    def setUp(self):
        super(CreateBackupTestsV239, self).setUp()
        self.controller = create_backup.CreateBackupController()
        self.req = fakes.HTTPRequest.blank('', version='2.39')

    @mock.patch.object(common, 'check_img_metadata_properties_quota')
    @mock.patch.object(common, 'get_instance')
    def test_create_backup_no_quota_checks(self, mock_get_instance,
                                                 mock_check_quotas):
        # 'mock_get_instance' helps to skip the whole logic of the action,
        # but to make the test
        mock_get_instance.side_effect = webob.exc.HTTPNotFound
        metadata = {'123': 'asdf'}
        body = {
            'createBackup': {
                'name': 'Backup 1',
                'backup_type': 'daily',
                'rotation': 1,
                'metadata': metadata,
            },
        }
        self.assertRaises(webob.exc.HTTPNotFound,
                          self.controller._create_backup, self.req,
                          fakes.FAKE_UUID, body=body)
        # starting from version 2.39 no quota checks on Nova side are performed
        # for 'createBackup' action after removing 'image-metadata' proxy API
        mock_check_quotas.assert_not_called()
