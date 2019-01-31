#!/usr/bin/env python
import configparser
import requests
import graphitesend
from urlparse import urlparse
import sys
import json
from time import sleep
import re


#Presto provides REST API for accessing JMX properties. PrestodbEmitter accesses this REST API to extract JMX property values.
#PrestodbEmitter class also emits those metrics on grpahite server using standard graphite protocol.
#This collects metrics including os metrics, node metrics, garbage collector metrics, qeury metrics, task manager/executor metrics,
#cluster manager metrics etc. To send prestodb metrics application is using graphitesend as plugin and it should be installed before running app.
#requirement can be installed using 'sudo pip install graphitesend'
#Usage : ./prestodb-graphite-emitter.py.py <Prestodb host> <Prestodb port> <Graphite host> <graphite port(carbon-cache line receiver port)> <time interval in seconds>
class PrestodbEmitter:

    # PrestodbEmitter constructor which accepts presto and
    def __init__(self, config_path):
        self.config = configparser.ConfigParser()
        self.read_properties(config_path)

    # Reading config file and parsing provided configurations
    def read_properties(self, path):
        self.config.read(path)
        self.presto_coord_url = "http://" + self.config['PRESTO_COORDINATOR']['IP'] + ":" + self.config['PRESTO_COORDINATOR']['PORT']
        self.node_path = self.config['PRESTO_COORDINATOR']['node_path']

    # Test function
    def print_some_data(self):
        print(self.config.sections())
        print(self.config['MBEAN_ALIAS']['g1_gc_young'])
        print(self.config['PRESTO_COORDINATOR']['mbean_path'])

    # PrestodbEmitter entry point function which gets executed at interval of time. Interval is is specified as 5th command line argument
    def run_emitter(self):
        self.cluster_node = self.presto_coord_url
        self.push_node_metrics("node_metrics")
        self.push_metrics("cluster_memory_manager", "memory_manager_metrics")
        self.push_metrics("query_manager", "query_manager_metrics")
        self.push_metrics("query_execution", "query_execution_metrics")
        self.push_metrics("task_manager", "task_manager_metrics")
        self.push_metrics("memory", "memory_usage_metrics")
        self.push_metrics("garbagecollector_g1_young_generation", "gc_g1_metrics.garbagecollector_g1_young_generation")
        self.push_metrics("garbagecollector_g1_old_generation", "gc_g1_metrics.garbagecollector_g1_old_generation")

        cluster_nodes = self.get_all_cluster_nodes()
        for node in cluster_nodes:
            print("Processing metrics for node...", node)
            if node == self.presto_coord_url:
                print("Not pushing metrics for this node, it is the coordinator and metrics have already been pushed!")
                continue
            self.cluster_node = node
            self.push_metrics("os", "os_metrics")
            self.push_metrics("task_executor", "task_executor_metrics")
            self.push_metrics("task_manager", "task_manager_metrics")
            self.push_metrics("memory", "memory_usage_metrics")
            self.push_metrics("garbagecollector_g1_young_generation", "gc_g1_metrics.garbagecollector_g1_young_generation")
            self.push_metrics("garbagecollector_g1_old_generation", "gc_g1_metrics.garbagecollector_g1_old_generation")

    # Get all cluster nodes
    def get_all_cluster_nodes(self):
        cluster_node_list = [self.presto_coord_url]
        json_metrics = self.get_node_json_metrics(self.presto_coord_url + self.node_path)
        for node_metrics in json_metrics:
            cluster_node_list.append(node_metrics["uri"])
        return cluster_node_list

    # This method collects cluster node metrics and sends it to graphite server
    def push_node_metrics(self, prefix):
        graphite_cli = self.get_graphite_sender("presto")
        json_metrics = self.get_node_json_metrics(self.presto_coord_url + self.node_path)
        if json_metrics is not None:
            for node_metrics in json_metrics:
                for node_metrics_attribute in json.loads(self.config['NODE_METRICS']['NODE_METRICS']):
                    node_url = urlparse(node_metrics["uri"])
                    graphite_cli.send(prefix + "." + node_url.netloc.replace(".", "_") + "." + node_metrics_attribute,node_metrics[node_metrics_attribute])
        return

    # Generic method takes mbean alias and graphite tag prefix and collects metrics for respective mbean
    def push_metrics(self, mbean_alias, prefix):
        graphite_cli = self.get_graphite_sender("presto")
        json_metrics = self.get_mbean_json_metrics(mbean_alias)
        if json_metrics is not None:
            filtered_metrics = dict()
            for attribute in json_metrics["attributes"]:
                if 'name' in attribute and 'value' in attribute:
                    filtered_metrics[attribute["name"]] = self.extract_value(attribute["value"])
            self.push_filtered_metrics(filtered_metrics, graphite_cli, prefix)
        return

    # This method extracts all required attrbute from JMX mbean REST API Response
    def extract_value(self, json_metrics):
        if isinstance(json_metrics, dict):
            if 'value' in json_metrics and 'key' in json_val:
                dict_metrics = {}
                dict_metrics['key'] = self.extract_value(json_metrics['value'])
                return dict_metrics
            else:
                obj_metrics = {}
                for k, v in json_metrics.items():
                    obj_metrics[k] = self.extract_value(v)
                return obj_metrics
        elif isinstance(json_metrics, list):
            list_metrics = {}
            for json_obj in json_metrics:
                if isinstance(json_obj, dict):
                    list_metrics[json_obj['key']] = self.extract_value(json_obj['value'])
            return list_metrics
        else:
            return json_metrics
        return

    # This method sends all extracted attributes to graphite server
    def push_filtered_metrics(self, json_metrics, graphite_cli, prefix):
        for k, v in json_metrics.items():
            key = prefix + "." + k
            if isinstance(v, dict):
                self.push_filtered_metrics(v, graphite_cli, key)
            elif isinstance(v, int):
                print(key + "\t: \t" + v)
                graphite_cli.send(key, v)
            elif isinstance(v, float):
                print(key + "\t: \t" + v)
                graphite_cli.send(key, v)
            else:
                continue
        return

    # Returns grphite client sender object
    def get_graphite_sender(self, prefix):
        return graphitesend.init(system_name=re.search('//(.+?):',self.cluster_node.replace(".", "_")).group(1), graphite_server=self.config['GRAPHITE']['IP'],
                                 graphite_port=int(self.config['GRAPHITE']['PORT']), prefix=prefix, fqdn_squash=True,
                                 lowercase_metric_names=True, asynchronous=False, timeout_in_seconds=5)

    # This method makes REST call to particular mbean type and returns json object
    def get_mbean_json_metrics(self, mbean_alias):
        response = requests.get(self.cluster_node + self.config['PRESTO_COORDINATOR']['mbean_path']
                                + self.config['MBEAN_ALIAS'][mbean_alias])
        return response.json()

    # This method makes REST call to Node API URL and returns json object
    def get_node_json_metrics(self, url):
        response = requests.get(url)
        return response.json()


# Main method which takes 2 parameters as commandline arguments (config file, iteration interval) and calls run_emitter of PrestodbEmitter class with specified interval of time
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: ./prestodb-graphite-emitter.py [Config file path] [Repeat Interval(seconds)]")
    else:
        emitter = PrestodbEmitter(sys.argv[1])
        print("Emitter started successfully!")
        while True:
            emitter.run_emitter()
            try:
		sleep(int(sys.argv[2]))
            except (KeyboardInterrupt, SystemExit):
                break
            continue
