# Alerting Lifecycle, Deduplication, Suppression & Routing

## 1. Alert Identity & Fingerprinting

To prevent alert fatigue and redundant notifications during storm events, every alert is assigned a deterministic SHA-256 fingerprint generated from stable dimensions:
$$\text{fingerprint} = \text{SHA256}(\text{org\_id} : \text{service} : \text{metric} : \text{rule\_name} : \text{severity})$$

Timestamps and ephemeral values are excluded so that identical firing occurrences match the existing record.

---

## 2. Alert Lifecycle & State Machine

Alerts progress through four states:
* `FIRING`: Alert condition is actively breached.
* `ACKNOWLEDGED`: Operator has recognized the alert and begun diagnosis.
* `RESOLVED`: Condition has returned to normal.
* `SUPPRESSED`: Muted by an active maintenance window or explicit policy.

When a duplicate firing event arrives:
* `alert.count += 1`
* `alert.last_seen_at = now()`
* An immutable `ALERT_DEDUPLICATED` event is appended to the timeline ledger.

---

## 3. Maintenance Windows & Suppression

* During an active maintenance window for a given service (or platform-wide), routine non-critical alerts transition to `SUPPRESSED`.
* **Security Critical Exemption**: Alerts categorized with severity `CRITICAL` are never suppressed by generic maintenance windows.
* Suppression is auditable: alert records remain in the database with status `SUPPRESSED`.

---

## 4. Alert Routing & Notification Abstraction

Routing matches alerts against `AlertRoutingRule` records filtering by:
* Service
* Severity
* Environment (`production`, `staging`)

Delivery is handled through `NotificationProvider` abstractions. The current production implementation is `InAppNotificationProvider`. Integrations with external vendors (PagerDuty, Slack, Opsgenie) are modeled purely as extensible provider abstractions.
