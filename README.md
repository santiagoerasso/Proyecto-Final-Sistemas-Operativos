# Proyecto final de Sistemas Operativos: Docker, Nginx, Prometheus y Grafana

Infraestructura académica con 3 instancias Flask, Nginx como proxy inverso y balanceador,
Nginx Prometheus Exporter, cAdvisor, Prometheus y Grafana con un dashboard preconfigurado.
Se utiliza una red Docker dedicada y volúmenes persistentes para Prometheus y Grafana.

## Requisitos previos

- Docker Desktop abierto (Windows con Linux containers / WSL2) o Docker Engine en Linux.
- Docker Compose V2 (`docker compose version`).
- PowerShell, terminal o Bash. k6 es opcional al iniciar y necesario para la prueba de carga desde el host.
- Puertos locales libres: **8888, 9091, 3001 y 8082**.

## Cómo levantar el proyecto

1. En el directorio raíz, copiar `.env.example` a `.env` y cambiar la contraseña local de Grafana.
   En PowerShell: `Copy-Item .env.example .env`
2. Ejecutar `docker compose config` (comprueba la configuración YAML).
3. Ejecutar `docker compose up -d --build`.
4. Verificar `docker compose ps` y después `docker compose logs --tail=50`.
5. Esperar a que Prometheus realice los primeros scrapes (intervalo configurado: 5s).

La primera compilación necesita internet para descargar las imágenes y dependencias Python.

## Direcciones de acceso desde el host

| Servicio | Dirección | Uso |
|---|---|---|
| Nginx | http://localhost:8888/ | Tráfico de aplicación / balanceo |
| Prometheus | http://localhost:9091/targets | Verificar 6 targets: 3 backend + Nginx Exporter + cAdvisor + Prometheus |
| Grafana | http://localhost:3001/ | Dashboard preconfigurado en **Proyecto Final SO** |
| cAdvisor | http://localhost:8082/ | Inspección de contenedores |

Grafana: ingresar con las credenciales definidas en `.env`. El dashboard debe aparecer en la carpeta **Proyecto Final SO**.

## Comprobar balanceo de carga

Cada respuesta de `/` incluye la clave JSON `instancia` ("1", "2" o "3").
En PowerShell (ejecutar desde el host):

```powershell
1..12 | ForEach-Object { (Invoke-RestMethod 'http://localhost:8888/').instancia } | Group-Object | Select-Object Name,Count
```

Alternativamente, visite 12 veces `http://localhost:8888/` y compruebe que las instancias se alternen.
El reparto round-robin predeterminado es aproximado bajo concurrencia y conexiones persistentes.

## Comprobar métricas

- En Prometheus > Targets, deberían aparecer **6 endpoints** en UP.
- En Prometheus > Graph, probar `up`, `nginx_up` y `nginx_http_requests_total`.
- Generar algunas solicitudes y probar `sum by(instance_id)(rate(backend_http_requests_total[1m]))`.
- Graficar p95: `histogram_quantile(0.95, sum by (le,instance_id) (rate(backend_http_request_duration_seconds_bucket[1m])))`.
- Para recursos de contenedores: `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, `container_network_receive_bytes_total`.

## Ejecutar prueba de carga desde la máquina física

Instalar k6 en Windows si aún no está disponible:

```powershell
winget install k6 --source winget
k6 version
```

Ejecutar desde la raíz del repositorio:

```powershell
k6 run .\pruebas\carga.js
```

El guion aumenta usuarios virtuales (10 → 30 → 50) y luego desciende a 0.
Al finalizar, registrar: total de solicitudes, tasa de errores, mediana y p95 de latencia,
y comparar con Grafana y Prometheus durante la carga. **No inventar resultados**.

## Comprobar el comportamiento ante fallos (adicional)

1. `docker compose stop backend1`
2. Seguir consultando `http://localhost:8888/`: deben responder backend2 y backend3.
3. Comprobar que Prometheus marca `backend1:5000` como DOWN.
4. `docker compose start backend1`
5. Confirmar recuperación del target y del reparto.

## Comandos de mantenimiento

```powershell
docker compose ps
docker compose logs -f nginx
docker compose logs -f prometheus
docker compose logs -f cadvisor
docker compose down
```

`docker compose down` detiene y elimina contenedores y red, pero conserva los volúmenes.
**No** usar `docker compose down -v` si se desean conservar las métricas y dashboards.

## Estructura

```text
backend/                     API, Dockerfile y dependencias
nginx/nginx.conf             Balanceo round-robin y stub_status
prometheus/prometheus.yml    Configuración de 6 targets
  grafana/provisioning/       Data source y proveedor de dashboards
  grafana/dashboards/         9 paneles preconfigurados
pruebas/carga.js             Prueba de carga k6 desde el host
INFORME_BORRADOR.md          Guía para completar informe con evidencias reales
GUION_VIDEO.md               Guía de demostración de máximo 10 minutos
```

## Notas técnicas

- Este despliegue es para un **entorno académico local**, no un sistema de producción.
- Los servicios accesibles desde el host se vinculan a `127.0.0.1` para evitar exposición a la red externa.
- cAdvisor requiere acceso privilegiado a métricas del daemon Docker; úsese solo en un host de confianza.
- En Windows + Docker Desktop/WSL2, algunas métricas y etiquetas de cAdvisor pueden faltar por limitaciones
  del sistema/versión. Documentar la observación y verificar el target `cadvisor` antes de concluir.
- Si hay contenedores del laboratorio anterior ocupando los puertos, deténgalos o cambie el puerto a la izquierda de `:`.
