# Scaling

`crocket_saturation` is one 0..1 gauge that says how close this instance is to its ceiling. Point an HPA or KEDA at it. Attach the `Metrics` fairing to serve it at `GET /metrics`.

## When to scale

| What you see | What it means | What to do |
| --- | --- | --- |
| Busy ratio or queue wait is high | Workers are full | Add pods |
| Event loop lag is high on an app that runs only on the loops | The loops are late. That can be a handler holding a loop, or CPU throttling from container limits. | Add pods, and check for CPU throttling |
| The pool input is pinned at 1.0 and the database is near its limit | More pods will not help | Scale the database. Compare `crocket_db_pool_wait_seconds` with the database's own CPU. |
| Shed, abandoned, or 504s are rising | Requests were shed, abandoned, or returned 504 | You scaled too late |
| `crocket_saturation` is steady and well under 0.7 | There is still headroom | No need to scale |

## What it measures

It is the largest of:

| Input | Counts as 1.0 at |
| --- | --- |
| `crocket_worker_busy_ratio` | every worker busy for the whole window |
| database pool connections in use / `crocket_db_pool_size` (with `crocket::db`) | every connection checked out |
| mean `crocket_request_queue_wait_seconds` in the window / 25 ms | 25 ms average wait for a worker |
| mean `crocket_event_loop_lag_seconds` in the window / 50 ms | loops 50 ms late on average |

Each input is capped at 1. The window is the time since the previous scrape of that `/metrics`, so scrape each pod from one Prometheus. Two scrapers would each see half windows. The pool share is read at scrape time. Taking the largest input means the first resource to run out drives it. Target about 0.7, to leave headroom for spikes.

CPU percent misleads for crocket, whose time is mostly kernel I/O. `crocket_worker_busy_ratio` counts handler time directly.

Handlers crocket places on the event loop (async ones, or fast plain functions) never use a worker, so an app that runs entirely on the loops shows up in event loop lag rather than in the busy ratio.

## Autoscaling

With [prometheus-adapter](https://github.com/kubernetes-sigs/prometheus-adapter), expose it as a pods metric and point an HPA at it:

```yaml
# prometheus-adapter rules
rules:
  - seriesQuery: 'crocket_saturation{namespace!="",pod!=""}'
    resources: {overrides: {namespace: {resource: namespace}, pod: {resource: pod}}}
    metricsQuery: 'max_over_time(crocket_saturation{<<.LabelMatchers>>}[1m])'
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: heroes}
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: heroes}
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Pods
      pods:
        metric: {name: crocket_saturation}
        target: {type: AverageValue, averageValue: "700m"}   # 0.7
```

Or with [KEDA](https://keda.sh), straight from Prometheus:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata: {name: heroes}
spec:
  scaleTargetRef: {name: heroes}
  minReplicaCount: 2
  maxReplicaCount: 20
  triggers:
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.monitoring:9090
        query: sum(avg_over_time(crocket_saturation{app="heroes"}[1m]))
        threshold: "0.7"   # per replica: KEDA divides the sum by the target
```

Useful PromQL alongside it:

```promql
# Worker busy share over 5 minutes, independent of scrape timing
sum by (pod) (rate(crocket_worker_busy_seconds_total[5m])) / sum by (pod) (crocket_workers)
# p95 wait for a worker
histogram_quantile(0.95, sum by (le) (rate(crocket_request_queue_wait_seconds_bucket[5m])))
# Already late: requests shed or abandoned per second
sum(rate(crocket_requests_shed_total[5m])) + sum(rate(crocket_requests_abandoned_total[5m]))
```
