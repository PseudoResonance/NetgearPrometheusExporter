#!/usr/bin/env python3

import asyncio
import argparse, sys, traceback, os

from lxml import html
import requests

from aiohttp import web

HOST = None
PORT = 15834
ENDPOINT = "http://192.168.100.1"
USERNAME = "admin"
PASSWORD = "password"

debug = False

def login():
  session = requests.Session()
  login_page = session.get(ENDPOINT + "/GenieLogin.asp")
  login_page_html = html.fromstring(login_page.text)
  web_token = login_page_html.xpath('/html/body/div/form/input[@name="webToken"]')[0].value
  post = session.post(ENDPOINT + "/goform/GenieLogin", data={'loginUsername': USERNAME, 'loginPassword': PASSWORD, 'login': "1", 'webToken': web_token})
  return session

def get_status(session):
  status_page = session.get(ENDPOINT + "/DocsisStatus.asp")
  status_page_html = html.fromstring(status_page.text)
  return status_page_html

async def parse_status(status):
  data = dict()
  data = await parse_table(data, status, "Startup Procedure", "startup_procedure_table")
  data = await parse_table(data, status, "Downstream Bonded Channels", "dsTable")
  data = await parse_table(data, status, "Upstream Bonded Channels", "usTable")
  data = await parse_table(data, status, "Downstream OFDM Channels", "d31dsTable")
  data = await parse_table(data, status, "Upstream OFDMA Channels", "d31usTable")
  return data

async def parse_table(data, status, table_name, table_id):
  data[table_name] = []
  columns = []
  valid_data = False
  for i, row in enumerate(status.xpath('//table[@id="' + table_id + '"]/tr')):
    if i > 0:
      row_data = dict()
      for i, col in enumerate(row.xpath("td")):
        row_data[columns[i]] = col.text
      data[table_name].append(row_data)
      valid_data = True
    else:
      for col in row:
        columns.append(col.text_content())
  if not valid_data:
    raise RuntimeError("Unable to fetch data")
  return data

async def fetch_data():
  try:
    session = login()
    status = get_status(session)
    return await parse_status(status)
  except:
    if debug:
      print("Unable to fetch new data")
      print(traceback.format_exc())
      sys.stdout.flush()
    return None

def setup_web():
  app = web.Application()
  app.add_routes([web.get("/", landing_handler)])
  app.add_routes([web.get("/metrics", web_handler)])
  return app

async def landing_handler(request):
  if debug:
    print("Received landing GET from " + request.remote)
    sys.stdout.flush()
  return web.Response(content_type='text/html',body='<!DOCTYPE html><title>Netgear Modem Exporter</title><h1>Netgear Modem Exporter</h1><p><a href="/metrics">Metrics</a></p>')

async def web_handler(request):
  if debug:
    print("Received GET from " + request.remote)
    sys.stdout.flush()
  data_string = ""
  data = await fetch_data()
  if data is None:
    raise web.HTTPBadGateway()
  
  # Startup Procedure
  for entry in data["Startup Procedure"]:
    match entry["Procedure"]:
      case "Acquire Downstream Channel":
        data_string += "# HELP downstream_channel_frequency Frequency of downstream channel in Hz" + "\n"
        data_string += "# TYPE downstream_channel_frequency gauge" + "\n"
        data_string += "downstream_channel_frequency{locked=\"" + ("0" if "not" in entry["Comment"].lower() else "1") + "\"} " + entry["Status"][:-3] + "\n"
      case "Connectivity State":
        data_string += "# HELP connectivity_state_status Modem connectivity status, 1 if connected" + "\n"
        data_string += "# TYPE connectivity_state_status untyped" + "\n"
        data_string += "connectivity_state_status{comment=\"" + entry["Comment"] + "\"} " + ("1" if "ok" in entry["Status"].lower() else "0") + "\n"
      case "Boot State":
        data_string += "# HELP boot_state_status Modem boot status, 1 if operational" + "\n"
        data_string += "# TYPE boot_state_status untyped" + "\n"
        data_string += "boot_state_status{comment=\"" + entry["Comment"] + "\"} " + ("1" if "ok" in entry["Status"].lower() else "0") + "\n"
      case "Configuration File":
        data_string += "# HELP configuration_file_status Modem configuration file status, 1 if ok" + "\n"
        data_string += "# TYPE configuration_file_status untyped" + "\n"
        data_string += "configuration_file_status{configuration_file=\"" + entry["Comment"].replace("\\", "\\\\") + "\"} " + ("1" if "ok" in entry["Status"].lower() else "0") + "\n"
      case "Security":
        data_string += "# HELP security_status Modem security status, 1 if ok" + "\n"
        data_string += "# TYPE security_status untyped" + "\n"
        data_string += "security_status{security_type=\"" + entry["Comment"] + "\"} " + ("1" if "enable" in entry["Status"].lower() else "0") + "\n"
      case "IP Provisioning Mode":
        data_string += "# HELP ip_provisioning_mode Modem IP provisioning mode" + "\n"
        data_string += "# TYPE ip_provisioning_mode untyped" + "\n"
        data_string += "ip_provisioning_mode{status=\"" + entry["Status"] + "\",comment=\"" + entry["Comment"] + "\"} 1\n"
  
  # Downstream Bonded Channels
  data_string += "\n"
  data_string += "# HELP downstream_bonded_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE downstream_bonded_channel_frequency gauge" + "\n"
  for entry in data["Downstream Bonded Channels"]:
    data_string += "downstream_bonded_channel_frequency{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Frequency"][:-3] + "\n"
  data_string += "# HELP downstream_bonded_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE downstream_bonded_channel_power gauge" + "\n"
  for entry in data["Downstream Bonded Channels"]:
    data_string += "downstream_bonded_channel_power{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Power"][:-5] + "\n"
  data_string += "# HELP downstream_bonded_channel_snr Channel SNR/MER in dB" + "\n"
  data_string += "# TYPE downstream_bonded_channel_snr gauge" + "\n"
  for entry in data["Downstream Bonded Channels"]:
    data_string += "downstream_bonded_channel_snr{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["SNR / MER"][:-3] + "\n"
  data_string += "# HELP downstream_bonded_channel_unerrored_codewords Total codewords received without error" + "\n"
  data_string += "# TYPE downstream_bonded_channel_unerrored_codewords counter" + "\n"
  for entry in data["Downstream Bonded Channels"]:
    data_string += "downstream_bonded_channel_unerrored_codewords{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Unerrored Codewords"] + "\n"
  data_string += "# HELP downstream_bonded_channel_correctable_codewords Total codewords received requiring correction" + "\n"
  data_string += "# TYPE downstream_bonded_channel_correctable_codewords counter" + "\n"
  for entry in data["Downstream Bonded Channels"]:
    data_string += "downstream_bonded_channel_correctable_codewords{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Correctable Codewords"] + "\n"
  data_string += "# HELP downstream_bonded_channel_uncorrectable_codewords Total codewords received uncorrectable" + "\n"
  data_string += "# TYPE downstream_bonded_channel_uncorrectable_codewords counter" + "\n"
  for entry in data["Downstream Bonded Channels"]:
    data_string += "downstream_bonded_channel_uncorrectable_codewords{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Uncorrectable Codewords"] + "\n"
  
  # Upstream Bonded Channels
  data_string += "\n"
  data_string += "# HELP upstream_bonded_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE upstream_bonded_channel_frequency gauge" + "\n"
  for entry in data["Upstream Bonded Channels"]:
    data_string += "upstream_bonded_channel_frequency{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Frequency"][:-3] + "\n"
  data_string += "# HELP upstream_bonded_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE upstream_bonded_channel_power gauge" + "\n"
  for entry in data["Upstream Bonded Channels"]:
    data_string += "upstream_bonded_channel_power{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + entry["Power"][:-5] + "\n"
  
  # Downstream OFDM Channels
  data_string += "\n"
  data_string += "# HELP downstream_ofdm_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_frequency gauge" + "\n"
  for entry in data["Downstream OFDM Channels"]:
    active_subcarrier_number_range_dat = entry["Active Subcarrier Number Range"].split(" ~ ")
    data_string += "downstream_ofdm_channel_frequency{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\",active_subcarrier_range_min=\"" + active_subcarrier_number_range_dat[0] + "\",active_subcarrier_range_max=\"" + active_subcarrier_number_range_dat[1] + "\"} " + entry["Frequency"][:-3] + "\n"
  data_string += "# HELP downstream_ofdm_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_power gauge" + "\n"
  for entry in data["Downstream OFDM Channels"]:
    active_subcarrier_number_range_dat = entry["Active Subcarrier Number Range"].split(" ~ ")
    data_string += "downstream_ofdm_channel_power{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\",active_subcarrier_range_min=\"" + active_subcarrier_number_range_dat[0] + "\",active_subcarrier_range_max=\"" + active_subcarrier_number_range_dat[1] + "\"} " + entry["Power"][:-5] + "\n"
  data_string += "# HELP downstream_ofdm_channel_snr Channel SNR/MER in dB" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_snr gauge" + "\n"
  for entry in data["Downstream OFDM Channels"]:
    active_subcarrier_number_range_dat = entry["Active Subcarrier Number Range"].split(" ~ ")
    data_string += "downstream_ofdm_channel_snr{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\",active_subcarrier_range_min=\"" + active_subcarrier_number_range_dat[0] + "\",active_subcarrier_range_max=\"" + active_subcarrier_number_range_dat[1] + "\"} " + entry["SNR / MER"][:-3] + "\n"
  data_string += "# HELP downstream_ofdm_channel_unerrored_codewords Total codewords received without error" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_unerrored_codewords counter" + "\n"
  for entry in data["Downstream OFDM Channels"]:
    active_subcarrier_number_range_dat = entry["Active Subcarrier Number Range"].split(" ~ ")
    data_string += "downstream_ofdm_channel_unerrored_codewords{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\",active_subcarrier_range_min=\"" + active_subcarrier_number_range_dat[0] + "\",active_subcarrier_range_max=\"" + active_subcarrier_number_range_dat[1] + "\"} " + entry["Unerrored Codewords"] + "\n"
  data_string += "# HELP downstream_ofdm_channel_correctable_codewords Total codewords received requiring correction" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_correctable_codewords counter" + "\n"
  for entry in data["Downstream OFDM Channels"]:
    active_subcarrier_number_range_dat = entry["Active Subcarrier Number Range"].split(" ~ ")
    data_string += "downstream_ofdm_channel_correctable_codewords{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\",active_subcarrier_range_min=\"" + active_subcarrier_number_range_dat[0] + "\",active_subcarrier_range_max=\"" + active_subcarrier_number_range_dat[1] + "\"} " + entry["Correctable Codewords"] + "\n"
  data_string += "# HELP downstream_ofdm_channel_uncorrectable_codewords Total codewords received uncorrectable" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_uncorrectable_codewords counter" + "\n"
  for entry in data["Downstream OFDM Channels"]:
    active_subcarrier_number_range_dat = entry["Active Subcarrier Number Range"].split(" ~ ")
    data_string += "downstream_ofdm_channel_uncorrectable_codewords{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\",active_subcarrier_range_min=\"" + active_subcarrier_number_range_dat[0] + "\",active_subcarrier_range_max=\"" + active_subcarrier_number_range_dat[1] + "\"} " + entry["Uncorrectable Codewords"] + "\n"
  
  # Upstream OFDMA Channels
  data_string += "\n"
  data_string += "# HELP upstream_ofdma_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE upstream_ofdma_channel_frequency gauge" + "\n"
  for entry in data["Upstream OFDMA Channels"]:
    data_string += "upstream_ofdma_channel_frequency{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\"} " + entry["Frequency"][:-3] + "\n"
  data_string += "# HELP upstream_ofdma_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE upstream_ofdma_channel_power gauge" + "\n"
  for entry in data["Upstream OFDMA Channels"]:
    data_string += "upstream_ofdma_channel_power{number=\"" + entry["Channel"] + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if "not" in entry["Lock Status"].lower() else "1") + "\",modulation=\"" + entry["Modulation / Profile ID"] + "\"} " + entry["Power"][:-5] + "\n"
  
  return web.Response(text=data_string)

async def main():
  global debug, USERNAME, PASSWORD, ENDPOINT, HOST, PORT
  parser = argparse.ArgumentParser()
  parser.add_argument('-d', '--debug', action='store_true')
  parser.add_argument('-u', '--user', dest='username', default=USERNAME)
  parser.add_argument('-p', '--pass', dest='password', default=PASSWORD)
  parser.add_argument('--endpoint', default=ENDPOINT)
  parser.add_argument('--host', default=HOST)
  parser.add_argument('--port', default=PORT)
  args = parser.parse_args()
  debug = args.debug
  try:
    USERNAME = os.environ['MODEM_USERNAME']
  except KeyError:
    USERNAME = args.username
  try:
    PASSWORD = os.environ['MODEM_PASSWORD']
  except KeyError:
    PASSWORD = args.password
  try:
    ENDPOINT = os.environ['MODEM_ENDPOINT']
  except KeyError:
    ENDPOINT = args.endpoint
  try:
    HOST = os.environ['SERVER_HOST']
  except KeyError:
    HOST = args.host
  if HOST == "None":
    HOST = None
  try:
    PORT = os.environ['SERVER_PORT']
  except KeyError:
    PORT = args.port
  if debug:
    print("Debug output enabled")
    sys.stdout.flush()
  runner = web.AppRunner(setup_web())
  if debug:
    print("Setting up web app")
    sys.stdout.flush()
  await runner.setup()
  site = web.TCPSite(runner, HOST, PORT)
  if debug:
    print("Starting web app at " + str(HOST) + ":" + str(PORT))
    sys.stdout.flush()
  await site.start()
  await asyncio.Event().wait()

if __name__ == '__main__':
  asyncio.run(main())
