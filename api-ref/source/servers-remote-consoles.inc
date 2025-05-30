.. -*- rst -*-

=================
 Server Consoles
=================

Manage server consoles.

Create Console
==============

.. rest_method:: POST /servers/{server_id}/remote-consoles

.. note:: Microversion 2.6 or greater is required for this API.

The API provides a unified request for creating a remote console. The user can
get a URL to connect the console from this API. The URL includes the token
which is used to get permission to access the console. Servers may support
different console protocols. To return a remote console using a specific
protocol, such as VNC, set the ``protocol`` parameter to ``vnc``.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403), itemNotFound(404),
conflict(409), notImplemented(501)

Request
-------

.. rest_parameters:: parameters.yaml


   - server_id: server_id_path
   - remote_console: remote_console
   - protocol: remote_console_protocol
   - type: remote_console_type

**Example Get Remote VNC Console**

.. literalinclude:: ../../doc/api_samples/os-remote-consoles/v2.6/create-vnc-console-req.json
   :language: javascript

**Example Get Remote spice-direct Console**

*``spice-direct`` consoles were added in microversion 2.99.*

.. literalinclude:: ../../doc/api_samples/os-remote-consoles/v2.99/create-spice-direct-console-req.json
   :language: javascript

Response
--------

.. rest_parameters:: parameters.yaml

    - remote_console: remote_console
    - protocol: remote_console_protocol
    - type: remote_console_type
    - url: remote_console_url

**Example Get Remote VNC Console**

.. literalinclude:: ../../doc/api_samples/os-remote-consoles/v2.6/create-vnc-console-resp.json
   :language: javascript

**Example Get Remote spice-direct Console**

*``spice-direct`` consoles were added in microversion 2.99.*

.. literalinclude:: ../../doc/api_samples/os-remote-consoles/v2.99/create-spice-direct-console-resp.json
   :language: javascript

Show Console Connection Information
===================================

.. rest_method:: GET /os-console-auth-tokens/{console_token}

Given the console authentication token for a server, shows the related
connection information.

Nova HyperV driver has been removed therefore requests for RDP console connection
information will always return an http 400 error. Starting from microversion 2.31
it's available for all other console types.

Normal response codes: 200

Error response codes: badRequest(400), unauthorized(401), forbidden(403),
itemNotFound(404)

Request
-------

.. rest_parameters:: parameters.yaml

  - console_token: console_token


Response
--------

.. rest_parameters:: parameters.yaml

  - console: console
  - instance_uuid: instance_id_body
  - host: console_host
  - port: port_number
  - tls_port: tls_port_number
  - internal_access_path: internal_access_path

**Example Show Console Authentication Token**

.. literalinclude:: ../../doc/api_samples/os-console-auth-tokens/v2.31/get-console-connect-info-get-resp.json
   :language: javascript

**Example Console Connection Information for a spice-direct Console**

*``spice-direct`` consoles were added in microversion 2.99.*

.. literalinclude:: ../../doc/api_samples/os-console-auth-tokens/v2.99/get-console-connect-info-get-resp.json
   :language: javascript
