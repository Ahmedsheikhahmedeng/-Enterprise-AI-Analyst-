# Access Governance & Inactive Account Reviews

> [!NOTE]
> **Explicit Certification Boundary**: This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.

---

## 1. Access Review Campaigns

Access reviews provide periodic audit campaigns over organization members, roles, and effective privileges:

1. **Inactive Account Detection**: Accounts with no authenticated activity for greater than 90 days are automatically flagged with `flagged_inactive = True`.
2. **Review Recommendations**:
   - `PENDING`: Initial state upon campaign launch.
   - `CONFIRMED`: Active membership confirmed by reviewer.
   - `REVOKE_RECOMMENDED`: Flagged for review due to inactivity or excessive privilege.
   - `REVOKED`: Access revoked via authorized governance workflow.
   - `EXPIRED`: Campaign concluded without action.
3. **Non-Destructive Revocation**: Access review recommendations do not silently revoke access; they require governance confirmation or ticket dispatch.
