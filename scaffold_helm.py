import os

services = ['faust-worker', 'scoring-api', 'incident-api']
base_dir = 'infra/helm'

for svc in services:
    chart_dir = os.path.join(base_dir, svc)
    tpl_dir = os.path.join(chart_dir, 'templates')
    os.makedirs(tpl_dir, exist_ok=True)
    
    with open(os.path.join(chart_dir, 'Chart.yaml'), 'w') as f:
        f.write(f'''apiVersion: v2\nname: {svc}\ndescription: Helm chart for {svc}\nversion: 0.1.0\nappVersion: "1.0.0"\n''')
        
    with open(os.path.join(tpl_dir, 'Deployment.yaml'), 'w') as f:
        f.write(f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {svc}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {svc}
  template:
    metadata:
      labels:
        app: {svc}
    spec:
      containers:
        - name: {svc}
          image: "soc-triager/{svc}:latest"
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
''')

    with open(os.path.join(tpl_dir, 'Service.yaml'), 'w') as f:
        f.write(f'''apiVersion: v1
kind: Service
metadata:
  name: {svc}
spec:
  selector:
    app: {svc}
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
''')

    with open(os.path.join(tpl_dir, 'ConfigMap.yaml'), 'w') as f:
        f.write(f'''apiVersion: v1
kind: ConfigMap
metadata:
  name: {svc}-config
data:
  ENV: "production"
  LOG_LEVEL: "info"
''')

    with open(os.path.join(tpl_dir, 'HPA.yaml'), 'w') as f:
        metric = "cpu" if svc == "faust-worker" else "memory"
        f.write(f'''apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {svc}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {svc}
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: {metric}
      target:
        type: Utilization
        averageUtilization: 75
''')

print("Created Helm charts.")
