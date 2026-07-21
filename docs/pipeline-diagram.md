# Pipeline flow

The 11 Jenkins stages, and where the rollback branch diverges from the happy path.

```mermaid
flowchart TD
    A[1. Checkout] --> B[2. Lint - ruff]
    B --> C[3. Unit Tests - pytest]
    C --> D[4. Train Model]
    D --> E{5. Validate Metrics<br/>accuracy/precision/recall >= 0.95?}
    E -- no --> X1[Pipeline fails<br/>nothing built or deployed]
    E -- yes --> F[6. Build Docker Image<br/>tag: commit hash]
    F --> G[7. Security Scan - trivy]
    G --> H[8. Deploy - Ansible blue-green<br/>new color up, health-gated, then cutover]
    H --> I[9. Smoke Test - health_check.py]
    I -- healthy --> K[11. Notify: success]
    I -- unhealthy --> J[10. Rollback - rollback.sh<br/>revert to previous image, re-verify health]
    J --> L[11. Notify: rollback performed]

    style E fill:#fff3cd,stroke:#856404
    style I fill:#fff3cd,stroke:#856404
    style X1 fill:#f8d7da,stroke:#721c24
    style J fill:#f8d7da,stroke:#721c24
```

Two gates decide the outcome of every run:

- **Stage 5** is a hard gate: below threshold, the pipeline stops before an image is even built.
- **Stage 9** is a soft gate: a failed smoke test doesn't abort the pipeline, it routes into rollback so the pipeline always ends with a known-good version live and a notification sent either way.
