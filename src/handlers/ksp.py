import logging

from handlers import TODO_PATH, CDE_PATH, FIRS_PATH
from handlers.dummy import Dummy, DummyResponse
import devices
import config, features


_FIRST_CONTACT = '''
	<?xml version="1.0" encoding="UTF-8"?>
	<response>
		<total_count>0</total_count>
		<next_pull_time/>
		<items>
			<item action="UPLOAD" type="SCFG" key="KSP.upload.scfg" priority="50" is_incremental="false" sequence="0" url="$_SERVER_URL_$ksp/scfg"/>
			<item action="SET" type="SCFG" key="KSP.set.scfg" priority="600" is_incremental="false" sequence="0">$_SERVERS_CONFIG_$</item>
			<item action="UPLOAD" type="SNAP" key="KSP.upload.snap" priority="1100" is_incremental="false" sequence="0"
				 url="$_SERVER_URL_$FionaCDEServiceEngine/UploadSnapshot"/>
		</items>
	</response>
'''.replace('\t', '').replace('\n', '')

def _first_contact(request, device):
	# triggered actions:
	# - upload config, for debugging purposes (we can check the API urls config in the logs)
	# - update client API urls, customized for the particular client type
	# - upload snapshot -- it will include device serial and model for the kindles
	text = _FIRST_CONTACT \
				.replace('$_SERVER_URL_$', config.server_url(request)) \
				.replace('$_SERVERS_CONFIG_$', _servers_config(request, device))
	return bytes(text, 'UTF-8')

def _servers_config(request, device):
	is_kindle = device.is_kindle()
	server_url = config.server_url(request)
	def _url(x):
		# always drop the last / from the url
		# the kindle devices urls also need to include the service paths (FionaTodoListProxy, FionaCDEServiceEngine, etc)
		# the other clients seem to require urls without those paths
		return (server_url + x.strip('/')) if is_kindle else server_url[:-1]

	# we always need the todo and cde urls
	urls = [ '', 'url.todo=' + _url(TODO_PATH), 'url.cde=' + _url(CDE_PATH) ]

	if is_kindle:
		# cookie domains ensures we get the proper cookie and are able to identify the device
		urls.append('cookie.store.domains=.amazon.com,' + config.server_hostname)
		# we need these urls to intercept registration/deregistration calls,
		# so that we can update the client certificate
		urls.extend((
			'url.firs=' + _url(FIRS_PATH),
			'url.firs.unauth=' + _url(FIRS_PATH),
		))
	else:
		urls.append('url.firs=' + _url(FIRS_PATH))
		# not sure what this is for, but all non-kindle clients seem to have it
		urls.append('url.cde.nossl=' + _url(CDE_PATH))

	# all other clients queue up the logs upload commands
	if not features.allow_logs_upload:
		if is_kindle:
			ignore = config.server_url(request) + 'ksp/ignore'
			urls.extend((
				'url.messaging.post=' + ignore,
				'url.det=' + ignore,
				'url.det.unauth=' + ignore,
			))
		# else:
		# 	urls.extend((
		# 		'url.messaging.post=',
		# 		'url.det=',
		# 		'url.det.unauth=',
		# 	))

	urls.append('')
	return '\n'.join(urls)


class KSP_Handler (Dummy):
	def __init__(self):
		Dummy.__init__(self, 'ksp', '/ksp')

	def call(self, request, device):
		if request.path.startswith('/ksp/ignore'):
			return 200

		if request.command == 'PUT' and request.path == '/ksp/scfg':
			logging.debug("got client configuration:\n%s", request.body)
			return 200

		logging.warn("unknown /ksp call %s", request.path)
		return 200
