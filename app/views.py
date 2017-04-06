import base64
from app import app
from flask_jsonrpc import JSONRPC
from flask import request
import requests
import json
# This is the apikey you specify in the application details in everynet portal
from .config import APIKEY
import logging
import sys

app_state = {
    "led_color": "00ff00",
    "devices": {},
}

@app.route('/')
@app.route('/index')
def index():
    return "Hello, World!"


def request_downlink_for_dev(devid):
    app.logger.info("Requesting downlink for %s" % devid)

    url = "https://core.eu-west-1.everynet.io/v1/rpc"
    headers = {'content-type': 'application/json'}

    # Example echo method
    payload = {
        "method": "notify",
        "params": {
            "api_key": APIKEY,
            "dev_eui": devid,
        },
        "jsonrpc": "2.0",
        "id": 0,
    }
    response = requests.post(url, data=json.dumps(payload), headers=headers).json()
    app.logger.info("Downlink request response %s" % repr(response))


def request_downlink_for_all():
    for devid in app_state["devices"].keys():
        request_downlink_for_dev(devid)


@app.route('/setled/<devid>', methods=['GET', 'POST'])
def setleddev(devid):
    app.logger.info("devid={}".format(devid))
    if request.method == 'POST':
        app_state["led_color"] = request.form["setled"]
        request_downlink_for_dev(devid)
    return """
<p>Devices: {devlist}</p>
<form method="post">
    <input type="text" value="{ledvalue}" name="setled" />
    <input type="submit" value="Set" />
</form>
""".format(**{ "ledvalue": app_state["led_color"], "devlist": repr(app_state["devices"])})


@app.route('/setled', methods=['GET', 'POST'])
def setled():
    if request.method == 'POST':
        app_state["led_color"] = request.form["setled"]
        request_downlink_for_all()
    return """
<p>Devices: {devlist}</p>
<form method="post">
    <input type="text" value="{ledvalue}" name="setled" />
    <input type="submit" value="Set" />
</form>
""".format(**{ "ledvalue": app_state["led_color"], "devlist": repr(app_state["devices"])})


jsonrpc = JSONRPC(app, '/api', enable_web_browsable_api=True)
@jsonrpc.method('App.index')
def index():
    return u'Welcome to Flask JSON-RPC'

# https://everynet.atlassian.net/wiki/display/EP/Everynet+Core+API+v.1.0

@jsonrpc.method('join(dev_eui=str, dev_addr=str, dev_nonce=str, net_id=str)')
def lora_join(dev_eui, net_id, dev_nonce, dev_addr, cf_list=None, **kwargs):
    """This method is called by the Network in case of receiving a LoRaWAN Join-Request packet from an OTAA device.
    Application Server should process a join procedure and returns network session key and encrypted join-accept message.
The method is not called if app_key was provided to Network by the customer. In this case the Network process join procedure according to LoRaWAN Standard.
Join procedure should strictly follow the LoRaWAN 1.0 (section 6.2), please refer to the standard."""
    print("Got join request from %s in net %s (kwargs: %s)" % (dev_eui, net_id, repr(kwargs)))
    pass


@jsonrpc.method('uplink(dev_eui=str, dev_addr=str, rx_time=float, counter_up=int, port=int, encrypted_payload=str)')
def uplink(dev_eui, dev_addr, rx_time, counter_up, port, encrypted_payload, payload=None, radio=None, **kwargs):
    """This method is called by Network in case of uplink packet received from a device.
Core Server may call this methods in parallel, depends on the number of incoming packets.
The Network do not store user data, so in case of Application Server is down the data will be lost."""
    if payload:
        payload = base64.b64decode(payload)
    if not dev_eui in app_state["devices"]:
        app_state["devices"][dev_eui] = {}
    app_state["devices"][dev_eui]["uplink"] = payload
    print("Got uplink from %s (%s), payload: %s (kwargs: %s)" % (dev_eui, dev_addr, payload, repr(kwargs)))
    return u'ok'


@jsonrpc.method('outdated(dev_eui=str, dev_addr=str, rx_time=float, counter_up=int, port=int, encrypted_payload=str)')
def outdated(dev_eui, dev_addr, rx_time, counter_up, port, encrypted_payload, payload=None, radio=None, **kwargs):
    """If Application server was unavailable in time of uplink request, messages will be saved in outdated queue.
    When Application server recovers, all outdated messages will be delivered by method outdated with same parameters as uplink."""
    if payload:
        payload = base64.b64decode(payload)
    if not dev_eui in app_state["devices"]:
        app_state["devices"][dev_eui] = {}
    app_state["devices"][dev_eui]["uplink"] = payload
    print("Got outdated from %s (%s), payload: %s (kwargs: %s)" % (dev_eui, dev_addr, payload, repr(kwargs)))
    return u'ok'


@jsonrpc.method('post_uplink(dev_eui=str, dev_addr=str, rx_time=float, counter_up=int, port=int)')
def post_uplink(dev_eui, dev_addr, rx_time, counter_up, port, encrypted_payload=None, payload=None, radio=None, **kwargs):
    """This method is called by Network in couple seconds after receiving uplink packet from first Gateway.
Field 'radio' contains information from all gateways, which receives uplink packet.
Core Server may call this methods in parallel, depends on the number of incoming packets.
Method will be called even if packet doesn't content payload."""
    if payload:
        payload = base64.b64decode(payload)
    print("Got post_uplink from %s (%s), payload: %s (kwargs: %s)" % (dev_eui, dev_addr, payload, repr(kwargs)))
    return u'ok'


@jsonrpc.method('downlink(dev_eui=str, dev_addr=str, tx_time=float, counter_down=int, max_size=int)')
def downlink(dev_eui, dev_addr, tx_time, counter_down, max_size, **kwargs):
    """The downlink method is called by the Network in case of available downlink opportunity (reception window will be opened)
    for the specified device is upcoming"""
    print("Got downlink for %s (%s) max %d bytes to be sent at %s (counter: %s kwargs: %s)" % (dev_eui, dev_addr, max_size, tx_time, counter_down, repr(kwargs)))
    return {
        "pending": False,
        "confirmed": False,
        "payload": base64.b64encode(app_state["led_color"].encode('UTF-8')).decode('UTF-8'),
    }


@jsonrpc.method('status(dev_eui=str, dev_addr=str, battery=int, snr=int)')
def status(dev_eui, dev_addr, battery, snr, **kwargs):
    """Answer for device status request. Contain battery level and demodulation signal-to-noise ratio of last received by device packet."""
    print("Got status message from %s (%s), batt: %s snr: %s (kwargs: %s)" % (dev_eui, dev_addr, battery, snr, repr(kwargs)))
    return u'ok'
