# Task 2: Pod Autoscaling с Istio IngressGateway и Per-Pod Rate Limiting

## Описание

Horizontal Pod Autoscaling (HPA) на базе потребления памяти с частным Istio IngressGateway в качестве балансировщика нагрузки и per-pod rate limiting через Envoy local rate limit.

## Компоненты

- **Private Istio IngressGateway** - балансировщик нагрузки с экспортом метрик в Prometheus
- **StatefulSet** - приложение scaletestapp с Istio sidecar
- **HPA** - автомасштабирование по памяти (1-10 подов, target: 30Mi)
- **EnvoyFilter** - per-pod rate limiting (200 RPS на под)
- **Prometheus метрики** - доступны через порты 15020 и 15090

## Архитектура

```
External Traffic (NodePort 30000)
         ↓
Private IngressGateway (hpa-example namespace)
         ↓ (round-robin load balancing)
scaletestapp-service (ClusterIP)
         ↓
StatefulSet Pods (with Istio sidecar + rate limiting)
```

### Rate Limiting
- **Per-pod limit**: 200 RPS
- **Total capacity**: pod_count × 200 RPS
- **Algorithm**: Token bucket (Envoy local rate limit)
- **Response**: HTTP 429 when limit exceeded

## Установка

```bash
# Убедитесь, что Istio установлен в кластере
./install_hpa_example.sh
```

## Доступ

**Приложение:** `http://<MINIKUBE_IP>:30000/`  
**Prometheus метрики:** `http://<MINIKUBE_IP>:30000/stats/prometheus` (через port-forward на 15020)

```bash
# Прямой доступ к приложению
curl http://$(minikube ip):30000/

# Доступ к метрикам IngressGateway
kubectl port-forward -n hpa-example svc/private-ingressgateway 15020:15020
curl http://localhost:15020/stats/prometheus
```

## Просмотр метрик

### IngressGateway Metrics
```bash
# Port-forward для доступа к метрикам
kubectl port-forward -n hpa-example svc/private-ingressgateway 15020:15020

# Просмотр всех метрик
curl http://localhost:15020/stats/prometheus

# RPS метрики
curl http://localhost:15020/stats/prometheus | grep envoy_cluster_upstream_rq_total

# Rate limiting метрики
curl http://localhost:15020/stats/prometheus | grep rate_limit
```

### Ключевые метрики Envoy
- `envoy_cluster_upstream_rq_total` - общее количество запросов
- `envoy_http_local_rate_limit_rate_limited` - количество rate-limited запросов
- `envoy_http_local_rate_limit_ok` - запросы в пределах лимита
- `envoy_cluster_upstream_rq_xx` - коды ответов по категориям

## Мониторинг HPA

```bash
kubectl get hpa -n hpa-example scaletestapp-hpa -w
kubectl top pods -n hpa-example -l app=scaletestapp
kubectl get pods -n hpa-example -l app=scaletestapp
```

## Проверка Rate Limiting

```bash
# Тест с 300 запросами (при 1 поде: 200 успешных + 100 rate limited)
for i in {1..300}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://$(minikube ip):30000/
done | sort | uniq -c

# Ожидаемый результат при 1 поде:
# 200 200 (успешные)
# 100 429 (rate limited)
```

## Нагрузочное тестирование

```bash
# Интерактивный режим
locust -f locustfile.py --host=http://$(minikube ip):30000

# Headless режим (10 пользователей, 60 секунд)
locust -f locustfile.py --host=http://$(minikube ip):30000 \
  --users 10 --spawn-rate 5 --run-time 60s --headless
```

## Удаление

```bash
./uninstall_hpa_example.sh
```

## Масштабирование и Rate Limiting

| Pods | Total RPS Capacity | Behavior at 400 RPS |
|------|-------------------|---------------------|
| 1    | 200 RPS          | 200 success + 200 rate limited (429) |
| 2    | 400 RPS          | 400 success |
| 5    | 1000 RPS         | 400 success |
| 10   | 2000 RPS         | 400 success |

## Файлы

- `dynamic-hpa-example.yaml` - полная конфигурация (IngressGateway, StatefulSet, HPA, EnvoyFilter)
- `ISTIO_SETUP.md` - подробная документация по Istio setup
- `locustfile.py` - нагрузочное тестирование
- `install_hpa_example.sh` - скрипт установки
- `uninstall_hpa_example.sh` - скрипт удаления

## Дополнительная информация

См. `ISTIO_SETUP.md` для:
- Детальной архитектуры компонентов
- Prometheus queries примеров
- Troubleshooting guide
- Конфигурации метрик
