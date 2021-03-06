# Copyright 2016 Red Hat, Inc
# Copyright 2017 Rackspace Australia
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

"""Routines that bypass file-system checks."""

import errno
import os
import shutil

from oslo_utils import fileutils

from nova import exception
import nova.privsep


@nova.privsep.sys_admin_pctxt.entrypoint
def writefile(path, mode, content):
    if not os.path.exists(os.path.dirname(path)):
        raise exception.FileNotFound(file_path=path)
    with open(path, mode) as f:
        f.write(content)


@nova.privsep.sys_admin_pctxt.entrypoint
def chown(
    path: str, uid: int = -1, gid: int = -1, recursive: bool = False,
) -> None:
    if not os.path.exists(path):
        raise exception.FileNotFound(file_path=path)

    if not recursive or os.path.isfile(path):
        return os.chown(path, uid, gid)

    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for item in dirs:
            os.chown(os.path.join(root, item), uid, gid)
        for item in files:
            os.chown(os.path.join(root, item), uid, gid)


@nova.privsep.sys_admin_pctxt.entrypoint
def makedirs(path):
    fileutils.ensure_tree(path)


@nova.privsep.sys_admin_pctxt.entrypoint
def chmod(path, mode):
    if not os.path.exists(path):
        raise exception.FileNotFound(file_path=path)
    os.chmod(path, mode)


@nova.privsep.sys_admin_pctxt.entrypoint
def move_tree(source_path: str, dest_path: str) -> None:
    shutil.move(source_path, dest_path)


@nova.privsep.sys_admin_pctxt.entrypoint
def utime(path):
    if not os.path.exists(path):
        raise exception.FileNotFound(file_path=path)

    # NOTE(mikal): the old version of this used execute(touch, ...), which
    # would apparently fail on shared storage when multiple instances were
    # being launched at the same time. If we see failures here, we might need
    # to wrap this in a try / except.
    os.utime(path, None)


@nova.privsep.sys_admin_pctxt.entrypoint
def rmdir(path):
    if not os.path.exists(path):
        raise exception.FileNotFound(file_path=path)
    os.rmdir(path)


@nova.privsep.sys_admin_pctxt.entrypoint
def last_bytes(path, num):
    """Return num bytes from the end of the file, and remaining byte count.

    :param path: The file to read
    :param num: The number of bytes to return

    :returns: (data, remaining)
    """
    with open(path, 'rb') as f:
        try:
            f.seek(-num, os.SEEK_END)
        except IOError as e:
            # seek() fails with EINVAL when trying to go before the start of
            # the file. It means that num is larger than the file size, so
            # just go to the start.
            if e.errno == errno.EINVAL:
                f.seek(0, os.SEEK_SET)
            else:
                raise

        remaining = f.tell()
        return (f.read(), remaining)
