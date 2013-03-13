from .main import app
from flask import render_template, redirect, url_for, request
from batou.service import ServiceConfig

# Reference to the currently active service configuration.
service_config = None


@app.route('/')
def overview():
    return render_template('index.html', config=service_config)


@app.route('/service/load', methods=['POST'])
def load():
    global service_config
    service_config = ServiceConfig(request.form['path'], [])
    import pdb; pdb.set_trace() 
    service_config.scan()
    return redirect(url_for('overview'))
