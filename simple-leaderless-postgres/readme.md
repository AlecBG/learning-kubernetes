# Simple Postgres client

A rather simple (and slightly silly) implementation of a leaderless DB algorithm. This runs using Kubernetes version 1.21

To run, have `helm` installed along with `kubectl` talking to a kubernetes cluster and run
```
helm install postgres-client postgres-client/ --namespace=<desired-namespace> --set postgresPassword=<desired-password>
```

There is a replicated database storing names (strings) and ages (integers)

The client can send `GET` and `PUT` requests to the url
```
<LoadBalancerURL>/api
```
The `GET` requests should contain json data in their content
```
{"name": <desired name to look up>}
```
It will return, if present, the output
```
{"name": <desired name to look up>, "age": <the age>}
```
The `PUT` requests should contain json content of the form
```
{"name": <desired name to write>, "age": <desired age to write>}
```
Reads and writes are only successful if they are successful on greater than half of the database nodes.

Every day at midnight the counts in all tables is recorded and the tables are all dropped. (A rather dramatic way to deal with merge conflicts!)

This set-up assumes that you are using AWS, but only via the [storageclass](storage_class.yaml) template. Feel free to change this to be compatible with whatever cloud provider you are using, and change the storageClassName value in the [values.yaml file](postgres-client/values.yaml).

You will need to build the two Docker images for the [app](app-container) and the [cron job](cron-container) and specify the image names in the [values.yaml file](postgres-client/values.yaml).

