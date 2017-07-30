#!/usr/bin/env python
import json
import requests
import os
import graphitesend
from urlparse import urlparse
import sys
from time import sleep
from time import time

#Presto provides REST API for accessing JMX properties. PrestodbEmitter accesses this REST API to extract JMX property values.
#PrestodbEmitter class also emits those metrics on grpahite server using standard graphite protocol.
#This collects metrics including os metrics, node metrics, garbage collector metrics, qeury metrics, task manager/executor metrics,
#cluster manager metrics etc. To send prestodb metrics application is using graphitesend as plugin and it should be installed before running app.
#requirement can be installed using 'sudo pip install graphitesend'
#Usage : ./prestodb-graphite-emitter.py <Prestodb host> <Prestodb port> <Graphite host> <graphite port(carbon-cache line receiver port)> <time interval in seconds>
class PrestodbEmitter:

	#Presto provided jmx mbeans to get metrics, each mbean is appended to mbean_path to get respective metrics
	MBEAN_ALIAS = {
          'memory':'java.lang:type=Memory',
          'gc_cms':'java.lang:type=GarbageCollector,name=ConcurrentMarkSweep',
          'g1_gc_young':'java.lang:type=GarbageCollector,name=G1 Young Generation',
          'g1_gc_old':'java.lang:type=GarbageCollector,name=G1 Old Generation',
          'gc_parnew':'java.lang:type=GarbageCollector,name=ParNew',
          'os':'java.lang:type=OperatingSystem',
          'query_manager':'com.facebook.presto.execution:name=QueryManager',
          'query_execution':'com.facebook.presto.execution:name=QueryExecution',
          'node_scheduler':'com.facebook.presto.execution:name=NodeScheduler',
          'task_executor':'com.facebook.presto.execution:name=TaskExecutor',
          'task_manager':'com.facebook.presto.execution:name=TaskManager',
          'memory_pool_general':'com.facebook.presto.memory:type=MemoryPool,name=general',
          'memory_pool_reserved':'com.facebook.presto.memory:type=MemoryPool,name=reserved',
          'memory_pool_system':'com.facebook.presto.memory:type=MemoryPool,name=system',
          'cluster_memory_manager':'com.facebook.presto.memory:name=ClusterMemoryManager',         'cluster_memory_pool_general':'com.facebook.presto.memory:type=ClusterMemoryPool,name=general',
          'cluster_memory_pool_reserved':'com.facebook.presto.memory:type=ClusterMemoryPool,name=reserved',
          'cluster_memory_pool_system':'com.facebook.presto.memory:type=ClusterMemoryPool,name=system',
      }

	#OS metrics at this available for monitoring
	OS_METRICS = ["AvailableProcessors","CommittedVirtualMemorySize","OpenFileDescriptorCount","TotalSwapSpaceSize","FreeSwapSpaceSize","ProcessCpuTime","FreePhysicalMemorySize","TotalPhysicalMemorySize","SystemCpuLoad","ProcessCpuLoad","SystemLoadAverage"]

	#Cluster node metric attributes available for monitoring
	NODE_METRICS = ["recentRequests","recentFailures","recentSuccesses","recentFailureRatio"]

	#Presto JMX monitoring API mbean base path
	mbean_path = "/v1/jmx/mbean/"

	#Presto node monitoring path
	node_path = "/v1/node"

	#PrestodbEmitter constructor which accepts presto and
	def __init__(self, presto_ip, presto_port, graphite_ip, graphite_port):
		self.graphite_ip = graphite_ip
		self.graphite_port = int(graphite_port)
		self.presto_coord_url = "http://" + presto_ip + ":" + presto_port


	#PrestodbEmitter entry point function which gets executed at interval of time. Interval is is specified as 5th command line argument
	def run_emitter(self):
		self.cluster_node = self.presto_coord_url
		self.push_node_metrics("node_metrics")
		self.push_metrics("cluster_memory_manager", "cluster_memory_manager_metrics")
		self.push_metrics("query_manager", "query_manager_metrics")
		self.push_metrics("query_execution", "query_execution_metrics")
		
		cluster_nodes =  self.get_all_cluster_nodes()
		for node in cluster_nodes:
			self.cluster_node = node
			self.push_metrics("os","os_metrics")
			self.push_metrics("task_executor", "task_executor_metrics")
			self.push_metrics("task_manager", "task_manager_metrics")
			self.push_metrics("memory", "memory_usage_metrics")
			self.push_metrics("g1_gc_young", "gc_g1_metrics.g1_young_generation")
			self.push_metrics("g1_gc_old", "gc_g1_metrics.g1_old_generation")

	#Get all cluster nodes
	def get_all_cluster_nodes(self):
		cluster_node_list = [self.presto_coord_url]
		json_metrics = self.get_node_json_metrics(self.presto_coord_url + self.node_path)
		for node_metrics in json_metrics:
			cluster_node_list.append(node_metrics["uri"])
		return cluster_node_list

	#This method collects cluster node metrics and sends it to graphite server
	def push_node_metrics(self,prefix):
		graphite_cli = self.get_graphite_sender("presto")
		json_metrics = self.get_node_json_metrics(self.presto_coord_url + self.node_path)
		for node_metrics in json_metrics:
			for node_metrics_attribute in self.NODE_METRICS:
				node_url = urlparse(node_metrics["uri"])
				graphite_cli.send(prefix + "." + node_url.netloc.replace(".", "_") + "." + node_metrics_attribute, node_metrics[node_metrics_attribute])
		return

	#Generic method takes mbean alias and graphite tag prefix and collects metrics for respective mbean
	def push_metrics(self, mbean_alias, prefix):
		graphite_cli = self.get_graphite_sender("presto")
		json_metrics = self.get_mbean_json_metrics(mbean_alias)
		filtered_metrics = dict()
		for attribute in json_metrics["attributes"]:
			if 'name' in attribute and 'value' in attribute:
				filtered_metrics[attribute["name"]]= self.extract_value(attribute["value"])
		self.push_filtered_metrics(filtered_metrics, graphite_cli, prefix)
        	return

	#This method extracts all required attrbute from JMX mbean REST API Response
	def extract_value(self, json_metrics):
		if isinstance(json_metrics, dict):
			if 'value' in json_metrics and 'key' in json_val:
				dict_metrics = {}
				dict_metrics['key']= self.extract_value(json_metrics['value'])
				return  dict_metrics
			else:
				obj_metrics = {}
				for k,v in json_metrics.items():
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

	#This method sends all extracted attributes to graphite server
	def push_filtered_metrics(self, json_metrics, graphite_cli, prefix):
		for k,v in json_metrics.items():
			key = prefix + "." + k
			if isinstance(v, dict):
				self.push_filtered_metrics(v,graphite_cli, key)
			elif isinstance(v, int):
				print(key)
				graphite_cli.send(key, v)
			elif isinstance(v, float):
				print(key)
				graphite_cli.send(key, v)
			else:
				continue
		return

	#Returns grphite client sender object
	def get_graphite_sender(self, prefix):
		return graphitesend.init(system_name=self.cluster_node.replace(".", "_"),graphite_server=self.graphite_ip, graphite_port=self.graphite_port, prefix=prefix, fqdn_squash=True,lowercase_metric_names=True, asynchronous=True)

	#This method makes REST call to particular mbean type and returns json object
	def get_mbean_json_metrics(self, mbean_alias):
		response = requests.get(self.cluster_node + self.mbean_path + self.MBEAN_ALIAS[mbean_alias])
		return response.json()

	#This method makes REST call to Node API URL and returns json object
	def get_node_json_metrics(self, url):
		response = requests.get(url)
		return response.json()

#Main method which takes 5 parameters as commandline arguments and calls run_emitter of PrestodbEmitter class with specified interval of time
if __name__ == '__main__':

	if len(sys.argv) < 6:
		print "Usage: ./prestodb-graphite-emitter.py [Prestodb IP Address] [Prestodb Port] [Graphite IP Address] [Graphite Port] [Repeat Interval(seconds)]"
	else:
		emitter = PrestodbEmitter(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4])
		print("Emitter started successfully!")
		while True:
			emitter.run_emitter()
			try:
				sleep(int(sys.argv[5]))
			except (KeyboardInterrupt, SystemExit):
	      			break
           		continue
