from flask import Flask, render_template, make_response, request
from gevent.pywsgi import WSGIServer
import logging
import threading
import webbrowser
from werkzeug.debug import DebuggedApplication

logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/favicon.ico')
def favicon():
    return make_response()


def main():
    logging.basicConfig(level=logging.DEBUG)
    pipeline = DebuggedApplication(app, evalex=True)
    server = WSGIServer(('localhost', 8887), pipeline)
    server.start()
    # use ephemeral port for developer GUIs + start browser
    #webbrowser.open('http://localhost:%s/' % server.server_port)
    server.serve_forever()
