# Proyecto final de Sistemas Operativos: Docker, Nginx, Prometheus y Grafana

Infraestructura académica compuesta por **tres instancias Flask** identificables, **Nginx** como proxy inverso y balanceador de carga, **Nginx Prometheus Exporter**, **cAdvisor**, **Prometheus** y **Grafana** con dashboard preconfigurado. Los servicios utilizan una red Docker dedicada y volúmenes persistentes para Prometheus y Grafana.

## Requisitos previos

- Docker Desktop abierto (Windows con Linux containers/WSL2) o Docker Engine en Linux.
- Docker Compose V2 (`docker compose version`).
- PowerShell, terminal o Bash.
- Puertos locales disponibles: **8888**, **9091**, **3001** y **8082**.
- Acceso a internet para descargar imágenes y dependencias en la primera compilación.
- k6 puede ejecutarse mediante Docker (no necesita instalación en Windows).

## Levantar la infraestructura

Desde la raíz del repositorio, en PowerShell:

```powershell
Copy-Item .env.example .env
# Edita .env y establece una contraseña propia para Grafana.
docker compose config
docker compose up -d --build
docker compose ps
```

El archivo `.env` es local y está excluido mediante `.gitignore`. **No lo publiques**. La primera compilación puede tardar mientras se descargan imágenes y dependencias. Si necesitas investigar un fallo:

```powershell
docker compose logs --tail=50
```

## URLs de acceso desde el host

| Servicio | URL | Función |
|---|---|---|
| Nginx | http://localhost:8888/ | Acceso a la aplicación y balanceo |
| Prometheus | http://localhost:9091/targets | Estado de los seis targets |
| Grafana | http://localhost:3001/ | Dashboard **Proyecto Final SO** |
| cAdvisor | http://localhost:8082/ | Recursos de los contenedores |

En Grafana, inicia sesión con las credenciales configuradas en `.env`.

## Arquitectura

```text
Cliente / k6
     |
     v
Nginx :8888 (round-robin)
     |--------|--------|
     v        v        v
 Backend 1 Backend 2 Backend 3
     \        |       /
      \_______|______/
              |
         /metrics
              |
Prometheus <-- Nginx Exporter / cAdvisor
     |
     v
 Grafana :3001
```

Los servicios se comunican por la red Docker `observabilidad`. El `Dockerfile` del backend utiliza Python 3.12 y Gunicorn. `nginx/nginx.conf` define el grupo de upstreams y habilita `stub_status` para el exportador. Prometheus realiza scrapes cada cinco segundos.

## Verificar el balanceo de carga

En PowerShell:

```powershell
1..12 | ForEach-Object {
    (Invoke-RestMethod -Uri 'http://localhost:8888/').instancia
} | Group-Object | Select-Object Name,Count
```

Las respuestas contienen la propiedad `instancia`, que identifica los backends `1`, `2` y `3`. Nginx utiliza round-robin predeterminado; con múltiples conexiones el reparto puede no ser exactamente igual.

## Verificar el monitoreo

Abre http://localhost:9091/targets y comprueba los seis targets: tres backends, Nginx Exporter, cAdvisor y Prometheus. En la sección de consultas de Prometheus puedes ejecutar:

```promql
up
```

```promql
sum(up)
```

La segunda consulta debe devolver `6` cuando todos los targets están accesibles.

Para estudiar tráfico y latencia:

```promql
sum by(instance_id)(rate(backend_http_requests_total[1m]))
```

```promql
histogram_quantile(0.95, sum by(le,instance_id)(rate(backend_http_request_duration_seconds_bucket[1m])))
```

También pueden consultarse `nginx_up`, `nginx_http_requests_total`, `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes` y `container_network_receive_bytes_total`.

En Grafana, abre el dashboard **Proyecto Final SO** y selecciona un intervalo temporal que abarque las pruebas para visualizar solicitudes/s, latencia, CPU, memoria y métricas del proxy.

## Ejecutar prueba de carga con k6

El script `pruebas/carga.js` define cuatro etapas: **15 segundos hasta 10 VUs**, **20 segundos hasta 30 VUs**, **30 segundos hasta 50 VUs** y **10 segundos de descenso a 0 VUs**. La duración programada es **75 segundos**. Los umbrales son menos del 2 % de fallos HTTP y p95 inferior a 1.500 ms.

**Método probado en Windows con Docker Desktop**, desde PowerShell en la raíz del proyecto:

```powershell
docker run --rm `
  --add-host=host.docker.internal:host-gateway `
  -v "${PWD}:/proyecto:ro" `
  -e BASE_URL=http://host.docker.internal:8888 `
  grafana/k6 run /proyecto/pruebas/carga.js
```

`host.docker.internal` permite al contenedor k6 alcanzar Nginx en el host. No es necesario instalar k6 directamente en Windows.

Si ya tienes k6 instalado en tu máquina física, la alternativa es:

```powershell
k6 run .\pruebas\carga.js
```

### Resultados de la prueba del 17 de noviembre de 2026

| Indicador | Resultado |
|---|---:|
| Solicitudes HTTP | 8.259 |
| Solicitudes promedio por segundo (k6) | 109,89 |
| Latencia media HTTP (k6) | 30,24 ms |
| Latencia p95 HTTP (k6) | 44,8 ms |
| Latencia máxima HTTP (k6) | 107,1 ms |
| Solicitudes HTTP fallidas | 0 de 8.259 (0 %) |
| Checks correctos | 16.518 de 16.518 (100 %) |
| Pico de Nginx observado en Grafana | 140 solicitudes/s |
| Conexiones activas Nginx en el pico observado | 51 |
| p95 por backend reportado en Grafana | 24,3 ms (cada backend) |
| Targets activos | 6 de 6 |

En Grafana, a las 11:17:45 (hora local), los tres backends mostraron aproximadamente **46,3**, **46,7** y **46,3 solicitudes/s**, respectivamente. Los máximos y los valores medios de k6 y Grafana tienen distintos horizontes y metodologías de agregación; no deben tratarse como la misma medición.

## Comprobar continuidad ante una falla (prueba adicional)

```powershell
docker compose stop backend1
1..12 | ForEach-Object {
    $r = Invoke-RestMethod -Uri 'http://localhost:8888/'
    $r.instancia
}
```

En la prueba realizada, las doce solicitudes fueron respondidas por los backends 2 y 3 (seis por cada uno). Prometheus puede marcar temporalmente `backend1` como DOWN. Restaurar:

```powershell
docker compose start backend1
```

Después, comprobar que la instancia 1 vuelve a aparecer en las respuestas y que `sum(up)` retorna a `6`. Esta prueba demuestra la continuidad observada bajo ese fallo concreto; no certifica alta disponibilidad general.

## Mantenimiento

```powershell
docker compose ps
docker compose logs -f nginx
docker compose logs -f prometheus
docker compose logs -f cadvisor
docker compose down
```

`docker compose down` elimina contenedores y red, pero conserva los volúmenes persistentes. **No uses `docker compose down -v` si deseas conservar datos de Prometheus y Grafana**.

## Estructura del proyecto

```text
.env.example                         Variables de configuración de ejemplo
.gitignore                           Exclusiones locales
README.md                            Guía de reproducción
backend/Dockerfile                   Imagen de la aplicación
backend/app.py                       API Flask, endpoints y métricas
backend/requirements.txt            Dependencias Python
docker-compose.yml                   Definición de servicios y red
nginx/nginx.conf                     Proxy inverso, round-robin y stub_status
prometheus/prometheus.yml            Targets de monitoreo
grafana/provisioning/                Fuente de datos y carga automática del dashboard
grafana/dashboards/                  Dashboard JSON
pruebas/carga.js                     Escenario de prueba k6
```

Los resultados corresponden al entorno y condiciones de la prueba descrita y pueden variar en otros equipos.
