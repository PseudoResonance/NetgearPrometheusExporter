# Netgear Modem Prometheus Exporter

A Prometheus exporter for Netgear modems.

## Installation

A Dockerfile is provided to build a Docker container to run the exporter, however it can also be run outside Docker.

### Docker Quickstart Guide

1. Clone the repository to a directory of your choice.
2. From inside the directory, run `docker build -t netgearexporter:1.0 .` to build the Dockerfile.
3. Create an environment variable file, `.env` in the directory with the application, and configure it with your modem login credentials. (ex: `MODEM_PASSWORD=password123`)
4. If it builds successfully, run the exporter with `docker run -d --env-file ./.env -p 15834:15834 --restart=unless-stopped netgearexporter:1.0`

### Prerequisites

 - Python 3.10
 - LXML
 - Requests
 - AIOHTTP

## Configuration

The exporter can be configured with command line arguments, environment variables, or through the Python file itself.

Environment variables will override options configured in the Python file, while command line arguments override all other config options.

### Environment Variables

| Variable | Description |
| --- | --- |
| `MODEM_USERNAME` | Sets the Netgear login username |
| `MODEM_PASSWORD` | Sets the Netgear login password |
| `MODEM_ENDPOINT` | Sets the Netgear login page endpoint (ex: `http://192.168.100.1`) |
| `SERVER_HOST` | Sets the address to bind the webserver to, or `None` to bind to all addresses |
| `SERVER_PORT` | Sets the port to bind the webserver to |

### Command Line Arguments

| Short | Long | Description |
| --- | --- | --- |
| `-d` | `--debug` | Enables debug console output |
| `-u` | `--user` | Sets the Netgear login username |
| `-p` | `--pass` | Sets the Netgear login password |
| | `--endpoint` | Sets the Netgear login page endpoint (ex: `http://192.168.100.1`) |
| | `--host` | Sets the address to bind the webserver to, or `None` to bind to all addresses |
| | `--port` | Sets the port to bind the webserver to |
