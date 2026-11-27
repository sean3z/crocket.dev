# Scaling

`crocket_saturation` is one 0..1 gauge that answers a single question: will another pod help right now? Point an HPA or KEDA at it. Attach the `Metrics` fairing to serve it at `GET /metrics`.

It is built from two gauges crocket also exports:

```
crocket_saturation = crocket_pod_saturation * (1 - crocket_dependency_saturation)
```

- `crocket_pod_saturation` is pressure the pod owns: workers busy with real work, requests waiting for a worker, and late event loops.
- `crocket_dependency_saturation` is pressure from downstream: the database pool, time workers spend blocked on the database, and dependency timeouts.

Each gauge is clamped to 0..1, and so is the product. With a healthy database it equals pod saturation. With a saturated database it goes to 0, so the autoscaler does not add pods onto a database that is already the limit. Before this split, `crocket_saturation` was the largest of all the inputs below, pool included.

## When to scale

| What you see | What it means | What to do |
| --- | --- | --- |
| `crocket_saturation` is steady and well under 0.7 | There is still headroom | No need to scale |
| `crocket_saturation` near or above 0.7, with `crocket_pod_saturation` high and `crocket_dependency_saturation` low | The pod is the bottleneck | Add pods |
| Mean `crocket_event_loop_lag_seconds` approaching 50 ms, on an app that runs only on the loops | The loops are late | Add pods, and check for CPU throttling |
| `crocket_dependency_saturation` at 1.0 and `crocket_saturation` near 0, even with a long queue | The database is the bottleneck. More pods would only open more connections to it | Fix or scale the database, not the pods |
| `crocket_requests_shed_total` or `crocket_requests_abandoned_total` increasing, or 504s in `crocket_http_requests_total` | You scaled too late | You scaled too late |

A busy pod on a healthy database (pod about 0.9, dependency about 0.05) gives about 0.85: scale up. A slow or full database (dependency 1, pod anywhere) gives 0: hold. A long queue does not change that while the dependency is saturated, because the queue is workers stuck downstream. Before scaling the database out, compare `crocket_db_pool_wait_seconds` and `crocket_dependency_saturation` with the database's own CPU.

## What it measures

`crocket_pod_saturation` is the largest of:

| Input | Counts as 1.0 at |
| --- | --- |
| pod worker busy: `(worker busy time - dependency blocking time) / (window * workers)` | every worker busy for the whole window, not counting time blocked on the database |
| mean `crocket_request_queue_wait_seconds` in the window / 25 ms | 25 ms average wait for a worker |
| mean `crocket_event_loop_lag_seconds` in the window / 50 ms | loops 50 ms late on average |

`crocket_dependency_saturation` is the largest of:

| Input | Counts as 1.0 at |
| --- | --- |
| database pool connections in use / `crocket_db_pool_size` (with `crocket::db`) | every connection checked out |
| dependency blocking time / `(window * workers)` | every worker blocked on the database for the whole window |
| dependency deadlines in the window | one or more |

Taking the largest input means the first resource to run out drives each gauge. Each input is capped at 1. The window is the time since the previous scrape of that `/metrics`, so scrape each pod from one Prometheus. Two scrapers would each see half windows. The pool share is read at scrape time. Target about 0.7, to leave headroom for spikes.

### How the database dampens the signal

Time a worker spends waiting on the database counts twice. It is removed from pod worker busy, because a faster pod would not finish it sooner, and it is added to dependency blocking time. So a pod that is only waiting on Postgres reads low pod saturation and high dependency saturation, and `crocket_saturation` falls. `crocket_worker_busy_ratio` still reports handler time with that waiting left in, if you want the raw number.

Deadlines push dependency saturation straight to 1 for the scrape window they happen in, even when the pool still has free connections, because the dependency already failed to answer in time. Three things count:

- **Pool acquire timeout.** A request gave up waiting for a free `crocket::db` connection.
- **Statement canceled by the database.** Postgres returned SQLSTATE `57014`, such as from `statement_timeout`.
- **Client timeout.** An outbound `crocket::client` call timed out. Client calls suspend instead of blocking a worker, so their wait is not blocking time, but the timeout still counts.

With no deadline in the window, this input is 0. It does not depend on how long the window is.

**Scrape each pod directly, not through the load balancer.** Each scrape through a load balancer lands on a different pod. You'd get a random pod's saturation, and the window would no longer be the time since that pod's last scrape. On Kubernetes, Prometheus pod discovery already scrapes each pod directly. On ECS, run the [AWS Distro for OpenTelemetry](https://aws-otel.github.io/docs/getting-started/container-insights/ecs-prometheus) collector as a sidecar that scrapes `localhost:8000/metrics` in each task.

CPU percent misleads for crocket, whose time is mostly kernel I/O and waiting on the database. Pod worker busy counts handler time directly. The flip side: if you run more workers than CPU cores, CPU can hit its limit before every worker is busy, so pod saturation reads lower than CPU on CPU-heavy handlers.

Handlers crocket places on the event loop (async ones, or fast plain functions) never use a worker, so an app that runs entirely on the loops shows up in event loop lag rather than in worker busy.

See it measured on the [benchmarks page](/benchmarks/#scaling): a busy pod that should scale, and a slow database that shouldn't.

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
# Is it the pod or the database? Compare the two halves
max by (pod) (crocket_pod_saturation)
max by (pod) (crocket_dependency_saturation)
# Worker busy share over 5 minutes, independent of scrape timing
sum by (pod) (rate(crocket_worker_busy_seconds_total[5m])) / sum by (pod) (crocket_workers)
# p95 wait for a worker
histogram_quantile(0.95, sum by (le) (rate(crocket_request_queue_wait_seconds_bucket[5m])))
# Already late: requests shed or abandoned per second
sum(rate(crocket_requests_shed_total[5m])) + sum(rate(crocket_requests_abandoned_total[5m]))
```
