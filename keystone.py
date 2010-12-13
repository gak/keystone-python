#!/usr/bin/env python

import urlparse
import json
import hashlib
import urllib2
import cookielib
import gzip
import re
import multiprocessing
import time
import random


class API(object):

    def __init__(self, server):
        self._server = server
        self._cookiejar = cookielib.CookieJar()
        self._opener = \
            urllib2.build_opener(urllib2.HTTPCookieProcessor(self._cookiejar))
        self._headers = {}
        self._headers['Accept'] = 'application/json'
        self._headers['Content-Type'] = 'application/json'
        self._max_children = 10
        self._projects = {}

    def request(self, method, url, data=None, callback=None,
            pre_callback=None, args=None):

        server = self._server

        # See if we're referencing a project and adjust the base url
        # accordingly.
        if args:
            project_id = args.get('project_id', None)
            if project_id:
                server = self._projects[project_id]['instance_url']

        try:
            if args:
                url = url % args
        except TypeError:
            print url, args
            raise

        url = urlparse.urljoin(server, url)

        if isinstance(data, dict):
            data = {'data': data}
            data = json.dumps(data)

        args = (self._opener, method, url, data, self._headers, callback,
            pre_callback, args)

        if not callback:
            return API.real_request(*args)

        
        # limit concurrent requests
        p = multiprocessing.Process(target=API.real_request, args=args)
        while len(multiprocessing.active_children()) >= self._max_children:
            time.sleep(random.random() * 2)

        # occasionally the os fails os.fork(), this loop retries it
        while 1:
            try:
                p.start()
                break
            except OSError, e:
                print 'retrying after', e
                time.sleep(0.1)

        return p

    @staticmethod
    def real_request(opener, method, url, data, headers, callback,
            pre_callback, args):
        
        print('%(method)s %(url)s' % locals())

        request = urllib2.Request(url, data=data, headers=headers)
        request.get_method = lambda: method

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
            callback(data, args=args)
        
        return data

    @staticmethod
    def process_response_data(headers, data):
        if headers.get('content-encoding', None) == 'gzip':
            data = gzip.GzipFile(fileobj=StringIO.StringIO(data)).read()
        return data

    # Requests

    def login(self, username, password, **kwargs):
        return self.request('POST', '/session', {
            'username': username,
            'password': hashlib.md5(password).hexdigest(),
        }, **kwargs)
    
    def get_projects(self, **kwargs):
        return self.request('GET', '/projects', 
            pre_callback=self.get_projects_response, **kwargs)

    def get_projects_response(self, data):
        '''Store all projects and their instance_urls so that any future
           request to a particular project can have its url changed
           automatically for the user.'''
        for project in data['data']:
            assert(type(project['id'] == int))
            self._projects[project['id']] = project
        return data

    def get_blockheaders(self, project_id, **kwargs):
        url = '/'.join(('projects', '%(project_id)i', 'blockheaders'))
        return self.request('GET', url, args=locals(), **kwargs)

    def get_formtypeheaders(self, project_id, blockheader_id, **kwargs):
        url = '/'.join((
            'projects', '%(project_id)i',
            'blockheaders', '%(blockheader_id)i',
            'formtypeheaders'
            ))
        return self.request('GET', url, args=locals(), **kwargs)

    def get_filters(self, project_id, blockheader_id, formtypeheader_id,
            **kwargs):
        url = '/'.join((
            'projects', '%(project_id)i',
            'blockheaders', '%(blockheader_id)i',
            'formtypeheaders', '%(formtypeheader_id)i',
            'filters'
            ))
        return self.request('GET', url, args=locals(), **kwargs)

