# Incident Response Runbook — FlowForge Customer Success FTE

## Severity Levels

| Severity | Description | Response SLA | Examples |
|----------|-------------|-------------|---------|
| P1 (Critical) | Complete outage — FTE not responding | 15 minutes | All channels down, DB unreachable |
| P2 (High) | Single channel down or high error rate | 1 hour | Gmail webhook not receiving, WhatsApp 5xx |
| P3 (Medium) | Degraded performance, elevated latency | 4 hours | P95 > 5s, escalation rate > 40% |
| P4 (Low) | Minor issue, no customer impact | Next business day | Monitoring gaps, DLQ backlog |

---

## On-Call Checklist

When paged, check in this order:

```
1. Check Kubernetes pod status
2. Check API health endpoint
3. Check Kafka consumer lag
4. Check database connectivity
5. Review recent error logs
6. Check external APIs (Gmail, WhatsApp)
```

---

## Runbook: All Channels Down (P1)

**Symptoms**: No tickets being processed from any channel. `/health` returns non-200.

### Step 1 — Check pod status
```bash
kubectl get pods -n customer-success-fte
# Look for: CrashLoopBackOff, Error, Pending states
```

### Step 2 — Check API logs
```bash
kubectl logs -l component=api -n customer-success-fte --tail=100 | grep -E "ERROR|CRITICAL"
```

### Step 3 — Check database
```bash
kubectl exec -it postgres-0 -n customer-success-fte -- pg_isready
# If not ready:
kubectl rollout restart statefulset/postgres -n customer-success-fte
```

### Step 4 — Restart API pods
```bash
kubectl rollout restart deployment/fte-api -n customer-success-fte
kubectl rollout status deployment/fte-api -n customer-success-fte
```

### Step 5 — Verify recovery
```bash
curl https://support-api.flowforge.io/health
# Expected: {"status": "healthy", ...}
```

---

## Runbook: Gmail Channel Down (P2)

**Symptoms**: Emails not being processed. No new tickets from email.

### Diagnose
```bash
# Check Gmail webhook endpoint
curl -X POST https://support-api.flowforge.io/channels/gmail/webhook \
  -H "Content-Type: application/json" \
  -d '{"message": {"data": "test", "messageId": "test"}}'

# Check API logs for Gmail errors
kubectl logs -l component=api -n customer-success-fte | grep -i gmail
```

### Fix: Refresh OAuth token
```bash
# Run token refresh
kubectl exec -it $(kubectl get pod -l component=api -n customer-success-fte -o name | head -1) \
  -n customer-success-fte -- python -c "from src.channels.gmail import refresh_oauth_token; refresh_oauth_token()"
```

### Fix: Re-register Pub/Sub subscription
```bash
# Via admin endpoint
curl -X POST https://support-api.flowforge.io/channels/gmail/setup-pubsub \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Runbook: WhatsApp Channel Down (P2)

**Symptoms**: WhatsApp messages not received. Twilio/Meta webhooks not triggering.

### Diagnose
```bash
# Check webhook endpoint
curl https://support-api.flowforge.io/channels/whatsapp/webhook \
  -G --data-urlencode "hub.mode=subscribe" \
       --data-urlencode "hub.verify_token=$WHATSAPP_VERIFY_TOKEN" \
       --data-urlencode "hub.challenge=test123"
# Should return: test123

# Check logs
kubectl logs -l component=api -n customer-success-fte | grep -i whatsapp
```

### Fix: Verify Meta webhook configuration
1. Go to Meta Developer Portal
2. Navigate to WhatsApp → Configuration
3. Verify webhook URL: `https://support-api.flowforge.io/channels/whatsapp/webhook`
4. Click "Test" to send a test notification
5. Check "Verify Token" matches your `WHATSAPP_VERIFY_TOKEN` secret

### Fix: Re-subscribe webhook
```bash
curl -X POST "https://graph.facebook.com/v18.0/$WHATSAPP_PHONE_NUMBER_ID/subscribed_apps" \
  -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN"
```

---

## Runbook: High Escalation Rate (P3)

**Symptoms**: Escalation rate > 40% (target: < 25%)

### Diagnose
```bash
# Check escalation metrics
curl https://support-api.flowforge.io/metrics/channels

# Check DLQ for processing errors
kubectl exec kafka-0 -n kafka -- kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group fte-message-processor

# Review recent escalations
psql $DATABASE_URL -c "
  SELECT reason, COUNT(*)
  FROM escalations
  WHERE created_at > NOW() - INTERVAL '1 hour'
  GROUP BY reason
  ORDER BY COUNT(*) DESC
  LIMIT 10;"
```

### Possible causes and fixes

| Cause | Fix |
|-------|-----|
| Knowledge base out of date | Re-index product docs (see deployment guide) |
| New product questions without docs | Update product-docs.md and re-index |
| Overly aggressive escalation rules | Review escalation-rules.md |
| Claude/OpenAI API issues | Check API status pages, verify keys |

---

## Runbook: High Latency (P3)

**Symptoms**: P95 response time > 5 seconds (target: < 3s)

### Diagnose
```bash
# Check pod CPU/memory
kubectl top pods -n customer-success-fte

# Check database query times
psql $DATABASE_URL -c "
  SELECT query, mean_exec_time, calls
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;"

# Check Kafka consumer lag
kubectl exec kafka-0 -n kafka -- kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group fte-message-processor
```

### Fixes

```bash
# Scale up workers
kubectl scale deployment/fte-message-processor --replicas=6 -n customer-success-fte

# Scale up API pods
kubectl scale deployment/fte-api --replicas=6 -n customer-success-fte

# Check HPA status
kubectl get hpa -n customer-success-fte
```

---

## Runbook: Kafka Consumer Lag (P2-P3)

**Symptoms**: Messages queuing up; customers not getting responses.

### Diagnose
```bash
kubectl exec kafka-0 -n kafka -- kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group fte-message-processor
# Look for LAG > 100
```

### Fix: Scale workers
```bash
kubectl scale deployment/fte-message-processor --replicas=10 -n customer-success-fte
```

### Fix: Check for stuck messages
```bash
# Check DLQ for failed messages
kubectl exec kafka-0 -n kafka -- kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic fte.dlq \
  --from-beginning \
  --max-messages 10
```

---

## Runbook: Database Down (P1)

```bash
# 1. Check PostgreSQL pod
kubectl get pod postgres-0 -n customer-success-fte

# 2. Try restart
kubectl delete pod postgres-0 -n customer-success-fte  # StatefulSet will recreate

# 3. Check persistent volume
kubectl get pvc -n customer-success-fte

# 4. Check disk space
kubectl exec postgres-0 -n customer-success-fte -- df -h /var/lib/postgresql/data

# 5. If data corruption — restore from backup
# kubectl exec postgres-0 -- pg_restore -d fte_db /backup/latest.dump
```

---

## Useful Commands Quick Reference

```bash
# Pod status
kubectl get pods -n customer-success-fte

# Logs (last 100 lines)
kubectl logs -l component=api -n customer-success-fte --tail=100

# Exec into pod
kubectl exec -it <pod-name> -n customer-success-fte -- bash

# Scale deployment
kubectl scale deployment/<name> --replicas=<n> -n customer-success-fte

# Restart deployment
kubectl rollout restart deployment/<name> -n customer-success-fte

# Health check
curl https://support-api.flowforge.io/health

# Channel metrics
curl https://support-api.flowforge.io/metrics/channels

# DLQ count
kubectl exec kafka-0 -n kafka -- kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --group fte-dlq-monitor
```

---

## Post-Incident Review Template

After resolving a P1 or P2 incident, complete this template within 24 hours:

```
## Incident Review — [Date]

### Summary
What happened?

### Timeline
- HH:MM — First detection
- HH:MM — On-call paged
- HH:MM — Root cause identified
- HH:MM — Fix deployed
- HH:MM — Verified resolved

### Root Cause
Why did it happen?

### Customer Impact
- Channels affected:
- Duration of impact:
- Estimated tickets delayed:

### Resolution
What fixed it?

### Prevention
What changes prevent recurrence?

### Action Items
- [ ] Owner: Task — Due date
```
