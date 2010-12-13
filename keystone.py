#!/usr/bin/env python

import urlparse
import json
import hashlib
import urllib2
import cookielib
import gzip
import re
from multiprocessing import Process


class API(object):

    def __init__(self, server):
        self._server = server
        self._cookiejar = cookielib.CookieJar()
        self._opener = \
            urllib2.build_opener(urllib2.HTTPCookieProcessor(self._cookiejar))
        self._headers = {}
        self._headers['Accept'] = 'application/json'
        self._headers['Content-Type'] = 'application/json'

        self._projects = {}

    def request(self, method, url, data=None, callback=None,
            pre_callback=None):

        server = self._server

        # See if we're referencing a project and adjust the base_url
        # accordingly.
        m = re.match('/projects/(?P<project_id>[0-9^/]+)/.*', url)
        if m:
            project_id = int(m.group('project_id'))
            server = self._projects[project_id]['instance_url']

        url = urlparse.urljoin(server, url)
        print('%(method)s %(url)s' % locals())
        if isinstance(data, dict):
            data = {'data': data}
            data = json.dumps(data)

        args = (self._opener, method, url, data, self._headers, callback,
            pre_callback)

        if not callback:
            return API.real_request(*args)

        p = Process(target=API.real_request, args=args)
        p.start()
        return p

    @staticmethod
    def real_request(opener, method, url, data, headers, callback,
            pre_callback):
        request = urllib2.Request(url, data=data, headers=headers)
        request.get_method = lambda: method

        import time
        time.sleep(2)

        f = opener.open(request)
        headers = f.info()
        data = f.read()
        data = API.process_response_data(headers, data)

        try:
            data = json.loads(data)
        except ValueError:
            pass

        if pre_callback:
            data = pre_callback(data)

        if callback:
            callback(data)
        
        return data

    @staticmethod
    def process_response_data(headers, data):
        if headers.get('content-encoding', None) == 'gzip':
            data = gzip.GzipFile(fileobj=StringIO.StringIO(data)).read()
        return data

    # Requests

    def login(self, username, password, callback=None):
        return self.request('POST', '/session', {
            'username': username,
            'password': hashlib.md5(password).hexdigest(),
        }, callback=callback)
    
    def get_projects(self, callback=None):
        return self.request('GET', '/projects', callback=callback,
                pre_callback=self.get_projects_response)

    def get_projects_response(self, data):
        '''Store all projects and their instance_urls so that any future
           request to a particular project can have its url changed
           automatically for the user.'''
        for project in data['data']:
            assert(type(project['id'] == int))
            self._projects[project['id']] = project
        return data

    def get_blockheaders(self, project_id, callback=None):
        return self.request('GET', '/projects/%(project_id)i/blockheaders' %
            locals(), callback=callback)

