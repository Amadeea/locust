# encoding: utf-8

import csv, re, io, json, os.path, events
from time import time
from itertools import chain
from collections import defaultdict
from six.moves import StringIO, xrange
import six
import main
import tests_loader

from gevent import wsgi
from flask import Flask, make_response, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename

from . import runners, configuration
from .cache import memoize
from .runners import MasterLocustRunner
from locust.stats import median_from_dict
from locust import __version__ as version
import gevent, itertools
import fileio
import base64

import logging
logger = logging.getLogger(__name__)

from csv_to_json import csvToJson

DEFAULT_CACHE_TIME = 2.0

app = Flask(__name__)
app.debug = True
app.root_path = os.path.dirname(os.path.abspath(__file__))
_ramp = False
greenlet_spawner = None
load_config=""
csv_stream = None

locustfile = None

@app.route('/')
def index():
    is_distributed = isinstance(runners.locust_runner, MasterLocustRunner)
    if is_distributed:
        slave_count = runners.locust_runner.slave_count
    else:
        slave_count = 0
    
    if runners.locust_runner.host:
        host = runners.locust_runner.host
    elif len(runners.locust_runner.locust_classes) > 0:
        host = runners.locust_runner.locust_classes[0].host
    else:
        host = None

    if runners.locust_runner.running_type == runners.NORMAL:
        edit_label = "Edit"
    else:
        edit_label = ""

    pages = tests_loader.populate_directories(fileio.os_path(),'tests/pages/')
    modules = tests_loader.populate_directories(fileio.os_path(),'tests/modules/')
    modules.update(pages)
    directories = modules
    
    return render_template("index.html",
        state=runners.locust_runner.state,
        is_distributed=is_distributed,
        slave_count=slave_count,
        user_count=runners.locust_runner.user_count,
        available_locustfiles = sorted(runners.locust_runner.available_locustfiles.keys()),
        test_file_directories = sorted(directories),
        version=version,
        ramp = _ramp,
        host=host
    )

@app.route('/new', methods=["POST"])
def newtest():
    runners.locust_runner.state = runners.STATE_INIT
    return index()

@app.route('/swarm', methods=["POST"])
def swarm():
    assert request.method == "POST"

    locust_count = int(request.form["locust_count"])
    hatch_rate = float(request.form["hatch_rate"])
    type_swarm = str(request.form["type_swarm"])
    global locustfile
    
    if type_swarm == "start":
        locustfile = request.form["locustfile"]
    
    assert locustfile in runners.locust_runner.available_locustfiles
    runners.locust_runner.select_file(locustfile)
    runners.locust_runner.start_hatching(locust_count, hatch_rate)

    response = make_response(json.dumps({'success':True, 'message': 'Swarming started'}))
    response.headers["Content-type"] = "application/json"
    return response

@app.route('/stop')
def stop():
    runners.locust_runner.stop()
    response = make_response(json.dumps({'success':True, 'message': 'Test stopped'}))
    response.headers["Content-type"] = "application/json"
    if greenlet_spawner != None:
        greenlet_spawner.kill(block=True)
    return response

@app.route("/stats/reset")
def reset_stats():
    runners.locust_runner.stats.reset_all()
    return "ok"

@app.route("/stats/requests/csv")
def request_stats_csv():
    rows = [
        ",".join([
            '"Method"',
            '"Name"',
            '"# requests"',
            '"# failures"',
            '"Median response time"',
            '"Average response time"',
            '"Min response time"',
            '"Max response time"',
            '"Average Content Size"',
            '"Requests/s"',
        ])
    ]

    for s in chain(_sort_stats(runners.locust_runner.request_stats), [runners.locust_runner.stats.aggregated_stats("Total", full_request_history=True)]):
        rows.append('"%s","%s",%i,%i,%i,%i,%i,%i,%i,%.2f' % (
            s.method,
            s.name,
            s.num_requests,
            s.num_failures,
            s.median_response_time,
            s.avg_response_time,
            s.min_response_time or 0,
            s.max_response_time,
            s.avg_content_length,
            s.total_rps,
        ))

    response = make_response("\n".join(rows))
    file_name = "requests_{0}.csv".format(time())
    disposition = "attachment;filename={0}".format(file_name)
    response.headers["Content-type"] = "text/csv"
    response.headers["Content-disposition"] = disposition
    return response

@app.route("/stats/distribution/csv")
def distribution_stats_csv():
    rows = [",".join((
        '"Name"',
        '"# requests"',
        '"50%"',
        '"66%"',
        '"75%"',
        '"80%"',
        '"90%"',
        '"95%"',
        '"98%"',
        '"99%"',
        '"100%"',
    ))]
    for s in chain(_sort_stats(runners.locust_runner.request_stats), [runners.locust_runner.stats.aggregated_stats("Total", full_request_history=True)]):
        if s.num_requests:
            rows.append(s.percentile(tpl='"%s",%i,%i,%i,%i,%i,%i,%i,%i,%i,%i'))
        else:
            rows.append('"%s",0,"N/A","N/A","N/A","N/A","N/A","N/A","N/A","N/A","N/A"' % s.name)

    response = make_response("\n".join(rows))
    file_name = "distribution_{0}.csv".format(time())
    disposition = "attachment;filename={0}".format(file_name)
    response.headers["Content-type"] = "text/csv"
    response.headers["Content-disposition"] = disposition
    return response

@app.route('/stats/requests')
@memoize(timeout=DEFAULT_CACHE_TIME, dynamic_timeout=True)
def request_stats():
    stats = []
    for s in chain(_sort_stats(runners.locust_runner.request_stats), [runners.locust_runner.stats.aggregated_stats("Total")]):
        stats.append({
            "method": s.method,
            "name": s.name,
            "num_requests": s.num_requests,
            "num_failures": s.num_failures,
            "avg_response_time": s.avg_response_time,
            "min_response_time": s.min_response_time or 0,
            "max_response_time": s.max_response_time,
            "current_rps": s.current_rps,
            "median_response_time": s.median_response_time,
            "avg_content_length": s.avg_content_length,
        })

    errors = [e.to_dict() for e in six.itervalues(runners.locust_runner.errors)]

    # Truncate the total number of stats and errors displayed since a large number of rows will cause the app
    # to render extremely slowly. Aggregate stats should be preserved.
    report = {"stats": stats[:500], "errors": errors[:500]}

    if stats:
        report["total_rps"] = stats[len(stats)-1]["current_rps"]
        report["fail_ratio"] = runners.locust_runner.stats.aggregated_stats("Total").fail_ratio
        if runners.locust_runner.state != ("stopped" or "ready"):
            # update run time
            runners.locust_runner.stats.total_run_time()
        report["total_run_time"] = runners.locust_runner.stats.run_time

        # since generating a total response times dict with all response times from all
        # urls is slow, we make a new total response time dict which will consist of one
        # entry per url with the median response time as key and the number of requests as
        # value
        response_times = defaultdict(int) # used for calculating total median
        for i in xrange(len(stats)-1):
            response_times[stats[i]["median_response_time"]] += stats[i]["num_requests"]

        # calculate total median
        stats[len(stats)-1]["median_response_time"] = median_from_dict(stats[len(stats)-1]["num_requests"], response_times)

    is_distributed = isinstance(runners.locust_runner, MasterLocustRunner)
    if is_distributed:
        report["slave_count"] = runners.locust_runner.slave_count

    report["state"] = runners.locust_runner.state
    report["user_count"] = runners.locust_runner.user_count
    report["running_type"] = runners.locust_runner.running_type
    report["host"] = runners.locust_runner.locust_classes[0].host
    return json.dumps(report)

@app.route("/exceptions")
def exceptions():
    response = make_response(json.dumps({
        'exceptions': [
            {
                "count": row["count"],
                "msg": row["msg"],
                "traceback": row["traceback"],
                "nodes" : ", ".join(row["nodes"])
            } for row in six.itervalues(runners.locust_runner.exceptions)
        ]
    }))
    response.headers["Content-type"] = "application/json"
    return response

@app.route("/exceptions/csv")
def exceptions_csv():
    data = StringIO()
    writer = csv.writer(data)
    writer.writerow(["Count", "Message", "Traceback", "Nodes"])
    for exc in six.itervalues(runners.locust_runner.exceptions):
        nodes = ", ".join(exc["nodes"])
        writer.writerow([exc["count"], exc["msg"], exc["traceback"], nodes])

    data.seek(0)
    response = make_response(data.read())
    file_name = "exceptions_{0}.csv".format(time())
    disposition = "attachment;filename={0}".format(file_name)
    response.headers["Content-type"] = "text/csv"
    response.headers["Content-disposition"] = disposition
    return response

@app.route("/ramp", methods=["POST"])
def ramp():
    from locust.ramping import start_ramping

    init_clients = int(request.form["init_count"])
    hatch_rate = int(request.form["hatch_rate"])
    hatch_stride = int(request.form["hatch_stride"])
    precision = int(request.form["precision"])
    max_clients = int(request.form["max_count"])
    response_time = int(request.form["response_time"])
    percentile = float(int(request.form["percentile"]) / 100.0)
    fail_rate = float(int(request.form["fail_rate"]) / 100.0)
    calibration_time = int(request.form["wait_time"])
    global greenlet_spawner
    greenlet_spawner = gevent.spawn(start_ramping, hatch_rate, max_clients, hatch_stride, percentile, response_time, fail_rate, precision, init_clients, calibration_time)
    response = make_response(json.dumps({'success':True, 'message': 'Ramping started'}))
    response.headers["Content-type"] = "application/json"
    return response


@app.route("/config/get_config_content", methods=["GET"])
def get_config_content():
    load_config = fileio.read(configuration.CONFIG_PATH)
    response = make_response(json.dumps({'data':load_config}))
    response.headers["Content-type"] = "application/json"
    return response

@app.route("/config/get_csv_column", methods=['POST'])
def config_csv():
    csvfile = request.files['csv_file']
    if not csvfile:
        return "No file"

    stream = io.StringIO(csvfile.stream.read().decode("UTF8"), newline=None)

    global csv_stream
    csv_stream = None
    csv_stream = csvToJson(stream)
    
    report = {}
    report['success'] = True
    report['columns'] = csv_stream.get_columns_name()
    response = make_response(json.dumps(report))
    response.headers["Content-type"] = "application/json"
    return response

@app.route("/config/convert_csv", methods=['POST'])
def convert_csv_to_json():
    try:
        multiple_data_headers = request.form.getlist('headers_checkbox')
        newpath_checkbox = request.form.getlist('new_path_checkbox')
        jsonpath = str(request.form['jsonpath'])
        options = request.form['json_option']
        config_text = request.form["multiple_form_final_json"]

        data_json = literal_eval(config_text)
        cc = configuration.ClientConfiguration()
        
        if cc.check_path_exist(data_json, jsonpath):
            print("data json : ", data_json)
            if jsonpath.strip() and options:
                global csv_stream
                report = {}
                report['success'] = True
                if(len(multiple_data_headers) > 0):
                    tempStr = csv_stream.convert(multiple_data_headers)
                    report['data'] = tempStr
                else:
                    tempStr = csv_stream.convert([])
                    if len(csv_stream.get_columns_name()) > 1:
                        report['data'] = tempStr
                    else:
                        report['data'] = tempStr.get(csv_stream.get_columns_name()[0])

                cc = configuration.ClientConfiguration()
                response = cc.update_json_config(data_json, report['data'], jsonpath, options, csv_stream.get_columns_name(), config_text)
                response.headers["Content-type"] = "application/json"
                
                return response
            else:
                response = make_response(json.dumps({'success':False, 'new_variable':False, 'message':'Please fill in or select required field.'}))
                response.headers["Content-type"] = "application/json"
            
        else:
            last_var_type = str(request.form["last_var_type"])
            
            data_json = cc.add_new_key(jsonpath, last_var_type, config_text)
            print("data_json : ",data_json)
            response = make_response(json.dumps({'success':False, 'new_variable':True, 'data':json.dumps(data_json, indent=4), 'multiple_data_headers':multiple_data_headers,
                'jsonpath':jsonpath, 'options':options, 'config_text':config_text}))
            response.headers["Content-type"] = "application/json"

        return response
    
    except Exception,e:
        if type(e).__name__ == 'BadRequestKeyError':
            response = make_response(json.dumps({'success':False, 'new_variable':False, 'message':'Please fill in or select required field.'}))
        else:
            response = make_response(json.dumps({'success':False, 'new_variable':False, 'message': str(e)}))
        response.headers["Content-type"] = "application/json"
       
        return response

@app.route("/config/validation/create_new_key", method=["POST"])
def validation_create_new_key():
    try:
        multiple_data_headers = request.form.getlist('headers_checkbox')
        newpath_checkbox = request.form.getlist('new_path_checkbox')
        jsonpath = request.form['jsonpath'])
        options = request.form['json_option']
        config_text = request.form["multiple_form_final_json"]
        last_var_type = str(request.form["last_var_type"])

        ClientConfiguration cc = new ClientConfiguration()
        data_json = cc.add_new_key(jsonpath, last_var_type, config_text)
        response = make_response(json.dumps({'success':True, 'data':json.dumps(data_json, indent=4)}))
        response.headers["Content-type"] = "application/json"
        return response

    except expression as identifier:
        pass
    
@app.route("/upload_file", methods=["POST"])
def upload_file():
    upload_directory = request.form.get('upload_directory')
    python_file = request.files['python_file']
    python_file_path = upload_directory + python_file.filename
    python_file_extension = os.path.splitext(python_file.filename)[1]
    python_file_content = python_file.read()
    if not python_file and python_file_extension != ".py":
        return expected_response({'success':False, 'message':"Can't upload this file. Please try again with python file with .py extension"})
    upload_status,upload_message = fileio.write(python_file_path, python_file_content)
    if upload_status is False :
        return expected_response({'success':False, 'message':upload_message})
    events.master_new_file_uploaded.fire(new_file={"full_path": python_file_path, "name": python_file.filename, "content":python_file_content})
    runners.locust_runner.reload_tests()
    return expected_response({'success':True, 'message':""})

def expected_response(json_dumps):
    response = make_response(json.dumps(json_dumps))
    response.headers["Content-type"] = "application/json"
    return response

@app.route("/config/save_json", methods=["POST"])
def save_json():
    assert request.method == "POST"
    config_json = str(request.form["final_json"])

    try:
        success, message =  fileio.write(configuration.CONFIG_PATH, config_json)
        events.master_new_configuration.fire(new_config=config_json)
        response = make_response(json.dumps({'success':success, 'message': message}))
    except Exception as err:
        response = make_response(json.dumps({'success':success, 'message': message}))

    response.headers["Content-type"] = "application/json"
    return response

def start(locust, options):
    global _ramp
    _ramp = options.ramp
    wsgi.WSGIServer((options.web_host, options.port), app, log=None).serve_forever()

def _sort_stats(stats):
    return [stats[key] for key in sorted(six.iterkeys(stats))]

def transform(text_file_contents):
    return text_file_contents.replace("=", ",")

def convert_csv():



