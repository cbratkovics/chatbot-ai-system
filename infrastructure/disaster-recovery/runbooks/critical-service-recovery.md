# Critical Service Recovery Runbook

## Overview
This runbook provides step-by-step procedures for recovering from critical service failures in the AI Chatbot System. It covers automated and manual recovery procedures, RTO/RPO objectives, and escalation paths.

## Severity Classification
- **P0 (Critical)**: Complete service outage affecting all users
- **P1 (High)**: Partial service degradation affecting >50% of users  
- **P2 (Medium)**: Limited service impact affecting <50% of users
- **P3 (Low)**: Minor issues with workarounds available

## Recovery Time Objectives (RTO)
- **P0**: 15 minutes
- **P1**: 1 hour
- **P2**: 4 hours
- **P3**: 24 hours

## Recovery Point Objectives (RPO)
- **Database**: 5 minutes (continuous replication)
- **File systems**: 1 hour (hourly backups)
- **Configuration**: Real-time (GitOps)

## Automated Recovery Procedures

### 1. Primary Region Failure (P0)

**Trigger Conditions:**
- Health checks failing for >3 minutes across all availability zones
- AWS region status indicating widespread issues
- Unable to reach any services in primary region

**Automated Response:**
```bash
# Automated failover will execute these steps:
1. Validate secondary region health
2. Promote read replica to primary database
3. Update Route53 DNS records
4. Scale up services in secondary region
5. Update load balancer configuration
```

**Manual Validation Required:**
- [ ] Verify DNS propagation (dig api.chatbot.com)
- [ ] Confirm database promotion successful
- [ ] Check application logs for errors
- [ ] Validate user authentication flow

### 2. Database Failure (P0/P1)

**Trigger Conditions:**
- Database connection failures >90%
- Replica lag >30 seconds
- Database CPU >95% for >5 minutes

**Automated Response:**
```bash
# For RDS failures:
1. Check replica health in other AZs
2. Promote healthy replica if available
3. Update application connection strings
4. Restart application pods to pick up new endpoints
```

**Manual Steps (if automation fails):**
```bash
# Connect to AWS Console or CLI
aws rds describe-db-instances --db-instance-identifier chatbot-prod

# If manual failover needed:
aws rds failover-db-cluster --db-cluster-identifier chatbot-cluster

# Update Kubernetes secrets with new endpoint
kubectl patch secret db-credentials -p '{"data":{"host":"<new-endpoint-base64>"}}'
kubectl rollout restart deployment/chatbot-api
```

### 3. Application Service Failure (P1)

**Trigger Conditions:**
- Pod crash loop backoff
- Health check failures >80%
- Memory/CPU resource exhaustion

**Automated Response:**
```bash
1. Restart failed pods
2. Scale up healthy pods
3. Update ingress to route around failed instances
4. Trigger horizontal pod autoscaler
```

**Manual Escalation:**
```bash
# Check pod status
kubectl get pods -n chatbot-production -l app=chatbot-api

# Check logs for errors
kubectl logs -n chatbot-production -l app=chatbot-api --tail=100

# Manual restart if needed
kubectl rollout restart deployment/chatbot-api -n chatbot-production

# Scale up if resource constrained
kubectl scale deployment/chatbot-api --replicas=10 -n chatbot-production
```

## Manual Recovery Procedures

### Complete Disaster Recovery (P0)

**When to Use:**
- Primary region completely unavailable
- Data center outage
- Major security breach requiring full rebuild

**Prerequisites:**
- [ ] Incident commander assigned
- [ ] Communication channels established
- [ ] Secondary region validated as healthy
- [ ] Backup integrity verified

**Step-by-Step Process:**

#### Phase 1: Assessment and Preparation (Target: 5 minutes)
1. **Assess Scope of Disaster**
   ```bash
   # Check region status
   aws ec2 describe-regions
   
   # Verify secondary region health
   curl -f https://us-west-2.api.chatbot.com/health
   ```

2. **Validate Secondary Region Resources**
   ```bash
   # Check RDS replicas
   aws rds describe-db-instances --region us-west-2
   
   # Check ECS/EKS cluster status
   aws eks describe-cluster --name chatbot-cluster --region us-west-2
   ```

3. **Notify Stakeholders**
   - Send incident notification via PagerDuty
   - Update status page: https://status.chatbot.com
   - Notify customer success team

#### Phase 2: Data Recovery (Target: 10 minutes)
1. **Promote Database Replica**
   ```bash
   # Promote read replica to master
   aws rds promote-read-replica \
     --db-instance-identifier chatbot-prod-replica-west \
     --region us-west-2
   
   # Wait for promotion to complete
   aws rds wait db-instance-available \
     --db-instance-identifier chatbot-prod-replica-west \
     --region us-west-2
   ```

2. **Update Database Connections**
   ```bash
   # Get new endpoint
   NEW_ENDPOINT=$(aws rds describe-db-instances \
     --db-instance-identifier chatbot-prod-replica-west \
     --region us-west-2 \
     --query 'DBInstances[0].Endpoint.Address' \
     --output text)
   
   # Update Kubernetes secrets
   kubectl create secret generic db-credentials \
     --from-literal=host=$NEW_ENDPOINT \
     --from-literal=username=postgres \
     --from-literal=password=$DB_PASSWORD \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

#### Phase 3: Application Recovery (Target: 10 minutes)
1. **Scale Up Secondary Region Services**
   ```bash
   # Update region in deployment
   kubectl patch deployment chatbot-api \
     -p '{"spec":{"template":{"spec":{"nodeSelector":{"topology.kubernetes.io/region":"us-west-2"}}}}}'
   
   # Scale up to full capacity
   kubectl scale deployment chatbot-api --replicas=20
   kubectl scale deployment websocket-service --replicas=10
   kubectl scale deployment auth-service --replicas=5
   ```

2. **Update Load Balancer Configuration**
   ```bash
   # Update ALB to point to secondary region
   aws elbv2 modify-target-group \
     --target-group-arn $TARGET_GROUP_ARN \
     --health-check-path /health \
     --region us-west-2
   ```

#### Phase 4: Traffic Failover (Target: 5 minutes)
1. **Update DNS Records**
   ```bash
   # Update Route53 to point to secondary region
   aws route53 change-resource-record-sets \
     --hosted-zone-id $HOSTED_ZONE_ID \
     --change-batch file://dns-failover.json
   ```

2. **Verify DNS Propagation**
   ```bash
   # Check DNS resolution
   dig api.chatbot.com
   nslookup api.chatbot.com 8.8.8.8
   ```

#### Phase 5: Validation and Monitoring
1. **Run Health Checks**
   ```bash
   # API health check
   curl -f https://api.chatbot.com/health
   
   # Database connectivity
   psql -h $NEW_ENDPOINT -U postgres -d chatbot -c "SELECT 1"
   
   # Authentication flow
   curl -X POST https://api.chatbot.com/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"testpass"}'
   ```

2. **Monitor Key Metrics**
   - Response time <2 seconds
   - Error rate <1%
   - Database connections healthy
   - Cache hit rate >80%

### Database Corruption Recovery (P1)

**When to Use:**
- Data corruption detected
- Inconsistent query results
- Index corruption

**Prerequisites:**
- [ ] Identify scope of corruption
- [ ] Locate clean backup point
- [ ] Calculate acceptable data loss

**Recovery Steps:**

1. **Stop Application Traffic**
   ```bash
   # Scale down to prevent further corruption
   kubectl scale deployment chatbot-api --replicas=0
   
   # Put maintenance page up
   kubectl apply -f maintenance-mode.yaml
   ```

2. **Assess Corruption Scope**
   ```bash
   # Run database integrity checks
   psql -h $DB_HOST -U postgres -d chatbot -c "REINDEX DATABASE chatbot;"
   
   # Check for corrupted tables
   psql -h $DB_HOST -U postgres -d chatbot -c "
   SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del 
   FROM pg_stat_user_tables 
   WHERE schemaname NOT IN ('information_schema', 'pg_catalog');"
   ```

3. **Restore from Backup**
   ```bash
   # Find latest clean backup
   aws s3 ls s3://ai-chatbot-backups/database-backups/ --recursive | sort | tail -5
   
   # Download backup
   aws s3 cp s3://ai-chatbot-backups/database-backups/chatbot_20241201_020000.sql.gz ./
   
   # Create new database for restore
   createdb -h $DB_HOST -U postgres chatbot_restore
   
   # Restore from backup
   gunzip -c chatbot_20241201_020000.sql.gz | psql -h $DB_HOST -U postgres chatbot_restore
   ```

4. **Validate Restored Data**
   ```bash
   # Run data consistency checks
   psql -h $DB_HOST -U postgres chatbot_restore -c "
   SELECT 
     (SELECT COUNT(*) FROM users) as user_count,
     (SELECT COUNT(*) FROM chat_sessions) as session_count,
     (SELECT COUNT(*) FROM messages) as message_count;"
   
   # Compare with expected counts
   # Check referential integrity
   psql -h $DB_HOST -U postgres chatbot_restore -f validate_integrity.sql
   ```

5. **Switch to Restored Database**
   ```bash
   # Rename databases
   psql -h $DB_HOST -U postgres -c "
   ALTER DATABASE chatbot RENAME TO chatbot_corrupted_$(date +%Y%m%d);
   ALTER DATABASE chatbot_restore RENAME TO chatbot;"
   
   # Restart applications
   kubectl scale deployment chatbot-api --replicas=10
   kubectl delete -f maintenance-mode.yaml
   ```

## Emergency Contacts and Escalation

### Primary On-Call Rotation
- **SRE Team**: +1-555-0100 (PagerDuty)
- **Database Team**: +1-555-0101 (PagerDuty) 
- **Security Team**: +1-555-0102 (PagerDuty)

### Escalation Matrix
| Time Elapsed | Action | Contact |
|--------------|--------|---------|
| 0-15 min | Primary on-call engineer | SRE rotation |
| 15-30 min | Escalate to senior SRE | SRE manager |
| 30-60 min | Engage incident commander | VP Engineering |
| 60+ min | Executive escalation | CTO, CEO |

### Communication Channels
- **Incident Channel**: #incident-response (Slack)
- **Status Updates**: #general (Slack)
- **Customer Comms**: support@chatbot.com
- **Executive Updates**: leadership@chatbot.com

## Post-Incident Procedures

### Immediate Actions (Within 2 hours)
1. **Restore Normal Operations**
   - Verify all systems healthy
   - Scale services to normal levels
   - Remove maintenance modes

2. **Customer Communication**
   - Update status page with resolution
   - Send customer notification email
   - Prepare customer success talking points

3. **Preserve Evidence**
   - Capture logs from incident timeframe
   - Take database/system snapshots
   - Document timeline of events

### Follow-up Actions (Within 24 hours)
1. **Incident Review Meeting**
   - Schedule within 24 hours
   - Include all responders
   - Review timeline and decisions

2. **Root Cause Analysis**
   - Technical analysis of failure
   - Process analysis of response
   - Identify improvement opportunities

3. **Post-Mortem Report**
   - Document timeline
   - Identify root causes
   - List action items with owners

### Long-term Actions (Within 1 week)
1. **Process Improvements**
   - Update runbooks based on learnings
   - Improve monitoring/alerting
   - Update automation scripts

2. **System Improvements**
   - Implement additional resilience
   - Update capacity planning
   - Enhance disaster recovery procedures

3. **Team Training**
   - Share lessons learned
   - Update training materials
   - Schedule practice drills

## Testing and Validation

### Monthly DR Tests
- **Scope**: Single service failover
- **Duration**: 30 minutes
- **Participants**: SRE team
- **Validation**: RTO/RPO metrics

### Quarterly DR Tests  
- **Scope**: Full region failover
- **Duration**: 2 hours
- **Participants**: All engineering teams
- **Validation**: End-to-end user flows

### Annual DR Tests
- **Scope**: Complete disaster scenario
- **Duration**: 4 hours
- **Participants**: All teams + executives
- **Validation**: Business continuity

### Test Checklist
- [ ] Backup/restore procedures
- [ ] Failover automation
- [ ] Communication procedures
- [ ] Monitoring and alerting
- [ ] Customer notification systems
- [ ] Data integrity validation
- [ ] Performance benchmarks
- [ ] Security controls

## Appendix

### A. Key Configuration Files
- DNS failover: `/runbooks/config/dns-failover.json`
- Maintenance mode: `/runbooks/config/maintenance-mode.yaml`
- Scaling profiles: `/runbooks/config/scaling-profiles.yaml`

### B. Monitoring Dashboards
- System health: https://grafana.chatbot.com/d/system-health
- DR metrics: https://grafana.chatbot.com/d/disaster-recovery
- Business metrics: https://grafana.chatbot.com/d/business-kpis

### C. Automated Scripts
- Region failover: `/scripts/failover-region.sh`
- Database promotion: `/scripts/promote-replica.sh`
- Service scaling: `/scripts/scale-services.sh`

### D. Backup Locations
- Database backups: `s3://ai-chatbot-backups/database-backups/`
- File system backups: `s3://ai-chatbot-backups/filesystem-backups/`
- Configuration backups: `s3://ai-chatbot-backups/config-backups/`

---

**Document Version**: 2.1  
**Last Updated**: 2024-01-15  
**Next Review**: 2024-04-15  
**Owner**: SRE Team  
**Approvers**: VP Engineering, CTO