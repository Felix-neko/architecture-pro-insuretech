# 2. Динамическое масштабирование контейнеров

## Подзадачи

### [2.1. Динамическое масштабирование на основании показателей утилизации памяти](task_2_1_simple_hpa_example/README.md)

Простой HPA (Horizontal Pod Autoscaler) на основе метрики потребления памяти. Приложение `scaletestapp` масштабируется при достижении целевого значения 24Mi памяти на под. Используется StatefulSet с LoadBalancer (NodePort 30000). 

**Ключевые особенности:**
- HPA по метрике памяти (target: 24Mi, limit: 64Mi)
- StatefulSet с Headless Service
- Нагрузочное тестирование через Locust
- Анализ поведения при OOM и автомасштабировании

---

### [2.2. Динамическое горизонтальное масштабирование на основании количества запросов в секунду](task_2_2_advanced_hpa_example/README.md)

Продвинутый HPA на основе кастомной метрики RPS (requests per second) с целевым значением 150 RPS на под. Используется Prometheus Adapter для преобразования метрик Istio в Custom Metrics API.

**Ключевые особенности:**
- HPA по кастомной метрике RPS через Prometheus Adapter
- Istio Service Mesh с частным IngressGateway (NodePort 30000)
- Envoy Sidecar Proxy с динамическим rate limiting (200 RPS на под)
- Полный стек мониторинга: Prometheus (NodePort 30003) +Grafana (NodePort 30004)
- АвтоматическийGrafana Dashboard для визуализации RPS метрик
- ServiceMonitor для сбора метрик Istio Gateway
