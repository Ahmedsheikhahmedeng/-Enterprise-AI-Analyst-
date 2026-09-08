# On-Call Schedules & Escalation Policies

## 1. On-Call Architecture

On-call rosters are structured as domain entities (`OnCallSchedule`) defining:
* Service assignment
* Active responder roster
* Rotation cadence and timezone

## 2. Escalation Policies

The platform supports tiered escalation (`EscalationPolicy`) to guarantee responder coverage:
* **Step 1**: Primary On-Call Responder (Service Owner)
* **Step 2**: Secondary Escalation (Platform / Infrastructure Engineer)
* **Step 3**: Incident Commander / SRE Lead

## 3. Implementation Boundary

* In accordance with enterprise specifications, external telephony and SMS alerting integrations (e.g. Twilio, PagerDuty, Opsgenie) are **modeled as abstractions**.
* Within the platform, assignments, notifications, and escalation events are tracked in-app via the SRE data store and audit timeline.
