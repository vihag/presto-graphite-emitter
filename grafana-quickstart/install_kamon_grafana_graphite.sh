#!/usr/bin/env bash
sudo docker pull kamon/grafana_graphite

docker run -d -p 80:80 -p 8125:8125/udp -p 8126:8126 -p 8000:8000 -p 2003:2003 -p 81:81 --name kamon-grafana-dashboard kamon/grafana_graphite

#username and password
#admin and admin

#Set Graphite Datasource
#Url Settings : Http : http://localhost:81