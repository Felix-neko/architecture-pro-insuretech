# Task 2: Pod Autoscaling с NGINX Ingress и Prometheus

## Описание

Horizontal Pod Autoscaling (HPA) на базе потребления памяти с NGINX Ingress Controller и экспортом метрик RPS в Prometheus через NodePort.

## Компоненты

- **NGINX Ingress Controller** (Helm) - маршрутизация трафика + метрики
- **StatefulSet** - приложение с предсказуемыми именами подов
- **HPA** - автомасштабирование по памяти (1-10 подов, target: 30Mi)
- **Prometheus метрики** - доступны через NodePort 30254

## Установка

```bash
./install_hpa_example.sh
```

## Доступ

**Приложение:** `http://scaletestapp.local:<INGRESS_PORT>`  
**Метрики:** `http://<MINIKUBE_IP>:30254/metrics`

Добавьте в `/etc/hosts`:
```
<MINIKUBE_IP> scaletestapp.local
```

## Просмотр метрик

```bash
# Быстрый просмотр
./view_metrics.sh

# Примеры запросов
./prometheus-metrics-examples.sh

# Прямой запрос
curl http://$(minikube ip):30254/metrics | grep nginx_ingress_controller_requests
```

## Мониторинг HPA

```bash
kubectl get hpa -n hpa-example -w
kubectl top pods -n hpa-example
```

## Нагрузочное тестирование

```bash
locust -f locustfile.py --host=http://scaletestapp.local:<INGRESS_PORT>
```

## Удаление

```bash
./uninstall_hpa_example.sh
```

## Основные метрики

- `nginx_ingress_controller_requests` - счетчик запросов (для RPS)
- `nginx_ingress_controller_request_duration_seconds` - latency
- `nginx_ingress_controller_response_size` - размер ответов
- `nginx_ingress_controller_bytes_sent` - отправленные байты

## Файлы

- `dynamic-hpa-example.yaml` - манифесты (Ingress, StatefulSet, HPA)
- `install_hpa_example.sh` - установка через Helm
- `uninstall_hpa_example.sh` - удаление
- `view_metrics.sh` - быстрый просмотр метрик
- `prometheus-metrics-examples.sh` - примеры работы с метриками
- `locustfile.py` - нагрузочное тестирование
