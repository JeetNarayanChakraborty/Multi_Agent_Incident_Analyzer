from Orchestrator import run_triage


def main():
    # Simulated PagerDuty Webhook v3 Payload (originally triggered by Datadog)
    pagerduty_payload = {
        "event": {
            "event_type": "incident.triggered",
            "data": {
                "id": "PD-INC-4092",
                "title": "P99 Latency on 'order-service' has spiked above 3000ms",
                "status": "triggered",
                "urgency": "high",
                "service": {"id": "PSV1234", "summary": "order-service"},
                "custom_details": {
                    "source_monitor": "Datadog APM",
                    "metric": "trace.http.request.p99",
                    "threshold_ms": 3000,
                    "current_value_ms": 4850,
                    "environment": "production",
                },
            },
        }
    }

    # Extract the relevant data from the JSON payload
    incident_data = pagerduty_payload["event"]["data"]
    custom_details = incident_data["custom_details"]

    # Format the payload into a structured directive for the LLM
    formatted_alert = (
        f"🚨 PAGERDUTY INCIDENT TRIGGERED 🚨\n"
        f"Incident ID: {incident_data['id']}\n"
        f"Title: {incident_data['title']}\n"
        f"Service: {incident_data['service']['summary']}\n"
        f"Environment: {custom_details['environment']}\n"
        f"Failing Metric: {custom_details['current_value_ms']}ms (Threshold: {custom_details['threshold_ms']}ms)\n\n"
        f"DIRECTIVE: Investigate this system state, identify the root cause dynamically, and dispatch an incident report."
    )

    # Trigger the LangGraph agent with the parsed alert
    run_triage(formatted_alert)


if __name__ == "__main__":
    main()
