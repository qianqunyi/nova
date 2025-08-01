# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
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

from oslo_config import cfg

base_options = [
    cfg.IntOpt(
        'password_length',
        default=12,
        min=0,
        help='Length of generated instance admin passwords.'),
    cfg.StrOpt(
        'instance_usage_audit_period',
        default='month',
        regex='^(hour|month|day|year)(@([0-9]+))?$',
        help='''
Time period to generate instance usages for. It is possible to define optional
offset to given period by appending @ character followed by a number defining
offset.

Possible values:

*  period, example: ``hour``, ``day``, ``month` or ``year``
*  period with offset, example: ``month@15`` will result in monthly audits
   starting on 15th day of month.
'''),
    cfg.BoolOpt(
        'use_rootwrap_daemon',
        default=False,
        help='''
Start and use a daemon that can run the commands that need to be run with
root privileges. This option is usually enabled on nodes that run nova compute
processes.
'''),
    cfg.StrOpt(
        'rootwrap_config',
        default="/etc/nova/rootwrap.conf",
        help='''
Path to the rootwrap configuration file.

Goal of the root wrapper is to allow a service-specific unprivileged user to
run a number of actions as the root user in the safest manner possible.
The configuration file used here must match the one defined in the sudoers
entry.
'''),
    cfg.StrOpt(
        'tempdir',
        help='Explicitly specify the temporary working directory.'),
    cfg.IntOpt(
        'default_green_pool_size',
        deprecated_for_removal=True,
        deprecated_since='32.0.0',
        deprecated_reason="""
This option is only used if the service is running in Eventlet mode. When
that mode is removed this config option will be removed too.
""",
        default=1000,
        min=100,
        help='''
The total number of coroutines that can be run via nova's default
greenthread pool concurrently, defaults to 1000, min value is 100. It is only
used if the service is running in Eventlet mode.
'''),
    cfg.IntOpt(
        'default_thread_pool_size',
        default=10,
        min=1,
        help='''
The total number of threads that can be run via nova's default
thread pool concurrently. It is only used if the service is running in
native threading mode.
'''),
    cfg.IntOpt(
        'cell_worker_thread_pool_size',
        default=5,
        min=1,
        help='''
The number of tasks that can run concurrently, one for each cell, for
operations requires cross cell data gathering a.k.a scatter-gather, like
listing instances across multiple cells. This is only used if the service is
running in native thread mode.
'''),
    cfg.IntOpt(
        'thread_pool_statistic_period',
        default=-1,
        min=-1,
        help='''
When new work is submitted to any of the thread pools nova logs the
statistics of the pool (work executed, threads available, work queued, etc).
This parameter defines how frequently such logging happens from a specific
pool in seconds. A value of 60 means that statistic will be logged
from a pool maximum once every 60 seconds. The value 0 means that logging
happens every time work is submitted to the pool. The value -1 means the
logging is disabled.
'''),
]


def register_opts(conf):
    conf.register_opts(base_options)


def list_opts():
    return {'DEFAULT': base_options}
