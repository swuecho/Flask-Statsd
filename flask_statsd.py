import re
import time
import socket
from flask import current_app, request
from flask import _app_ctx_stack as stack
from statsd import StatsClient


def _extract_request_path(url_rule):
    s = re.sub(r'/<.*>', '/', str(url_rule))
    s = re.sub(r'\.json$', '', s)
    return '.'.join(filter(None, s.split('/')))


def add_tags(path, **tags):
    if not tags:
        return path
    tag_str =','.join([('%s=%s' % (k, v)) for k, v in tags.items()])
    return '%s,%s' % (path, tag_str)


class FlaskStatsd(object):

    def __init__(self, host='localhost', port=8125, prefix='', app=None):
        self.app = app
        self.hostname = socket.gethostname()
        self.statsd_host = host
        self.statsd_port = port
        self.statsd_prefix = prefix
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        self.connection = self.connect()

    def connect(self):
        return StatsClient(host=self.statsd_host,
                           port=self.statsd_port,
                           prefix=self.app.name + self.statsd_prefix,
                           maxudpsize=1024)

    def before_request(self):
        ctx = stack.top
        ctx.request_begin_at = time.time()

    def after_request(self, resp):
        ctx = stack.top
        period = (time.time() - ctx.request_begin_at) * 1000
        status_code = resp.status_code
        print request.url_rule
        path = _extract_request_path(request.url_rule)
        with self.connection.pipeline() as pipe:
            pipe.incr(add_tags(path + ".count", server=self.hostname, status_code=status_code))
            pipe.timing(add_tags(path + ".time", server=self.hostname, status_code=status_code), period)
            pipe.incr(add_tags("request.count", server=self.hostname, status_code=status_code))
            pipe.timing(add_tags("request.time", server=self.hostname, status_code=status_code), period)

        return resp