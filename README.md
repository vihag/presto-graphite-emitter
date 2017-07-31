# Presto-Graphite-emitter

___

Graphite emitter/sink for Presto. It allows to send Presto co-ordinator, worker, query metrics to Graphite in plaintext format.

## Pre-Requisites
___

* Python 2.7 or above
* Below packages needs to be installed,
	* requests
	* graphitesend
* Graphite server 

Above python packages can be installed using below commands,

```bash
sudo pip -q install requests==2.8.1
sudo pip -q install graphitesend
```

Graphite installation instructions are available at [Graphite documentation](http://graphite.readthedocs.io/en/latest/install.html) 


## Getting Started & Usage
___

Presto graphite emitter is a python script which collects Presto metrics and emits them to Graphite server in plaintext format. Presto metrics are exposed using JMX MBeans. Available metrics are collected, transformed into required format and sent to graphite server. 

### Usage

After installation of required packages, presto metric emitter needs to 5 parameters, 
1. PrestoDB co-ordinator IP Address
2. PrestoDB co-ordinator Port
3. Graphite server IP Address
4. Graphite server Port
5. Interval

Interval (in seconds) will be used to periodically collect metrics. Below command can be used,

```
Syntax: 
nohup prestodb-graphite-emitter.py [Prestodb_CoOrd_IP] [Prestodb_CoOrd_Port] [Graphite_IP] [Graphite_Port] [Interval in sec] > nohup.out &

Example:
nohup prestodb-graphite-emitter.py 127.0.0.1 8285 127.0.0.1 2003 10 > nohup.out &

```

Emitted metrics will be in prefixed with nodenames to differentiate different worker nodes in cluster. Currently all metrics available via [Presto JMX](https://github.com/prestodb/presto/wiki/Monitoring) are supported and are configurable through prestodb-graphite-emitter.py script. 

Few important included metrics classes are,

```
query_manager
query_execution
node_scheduler
task_executor
task_manager
g1_gc_young
g1_gc_old
cluster_memory_manager
```

Separate metric configuration file and auto dependencies installation will be available in next version of this emitter. Emitted metrics can be viewed using Graphite or Grafana dashboards.
