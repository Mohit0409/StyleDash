"""Fail-closed, OFFLINE staging external-boundary release preflight.

This is a policy checker over sanitised metadata. It never reads secret values,
calls networks, logs into accounts, tests payment processors or changes services.

A green result is possible only when separate, real runtime probes have been
performed by an authorised reviewer and their boolean evidence is provided.
The checker itself cannot attest that those probes were actually performed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


DISABLED = {"false", "no", "off", "0"}
REQUIRED_DISABLED = (
    "STYLEDASH_ORDERING_ENABLED",
    "STYLEDASH_NTFY_ENABLED",
    "STYLEDASH_NTFY_BACKGROUND",
    "STYLEDASH_ENABLE_TEST_PRODUCT",
)
PROHIBITED_STAGING_KEY_NAMES = {
    "RAZORPAY_KEY_ID",
    "RAZORPAY_KEY_SECRET",
    "RAZORPAY_LIVE_KEY_ID",
    "RAZORPAY_LIVE_KEY_SECRET",
    "SMTP_PASSWORD",
    "BREVO_API_KEY",
    "SENDGRID_API_KEY",
}
PROD_PORTS = ("8080", "8081")


def check(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        raise TypeError("Snapshot must be a JSON object.")
    stage = snapshot.get("staging") if isinstance(snapshot.get("staging"), dict) else {}
    prod = snapshot.get("production") if isinstance(snapshot.get("production"), dict) else {}
    flags = snapshot.get("flags") if isinstance(snapshot.get("flags"), dict) else {}
    origin = snapshot.get("origin") if isinstance(snapshot.get("origin"), dict) else {}
    frontend_auth = snapshot.get("frontend_auth") if isinstance(snapshot.get("frontend_auth"), dict) else {}
    evidence = snapshot.get("runtime") if isinstance(snapshot.get("runtime"), dict) else {}
    listeners = snapshot.get("listeners") if isinstance(snapshot.get("listeners"), dict) else {}
    env_keys = snapshot.get("env_key_names")
    issues: list[str] = []
    if stage.get("ActiveState") != "active":
        issues.append("staging_not_active")
    if not stage.get("User") or not stage.get("Group"):
        issues.append("staging_identity_unknown")
    elif not prod.get("User") or not prod.get("Group"):
        issues.append("production_identity_unknown")
    elif stage["User"] == prod["User"] or stage["Group"] == prod["Group"]:
        issues.append("staging_shares_production_identity")
    if stage.get("EnvironmentFileStageScoped") is not True or stage.get("EnvironmentFileMentionsProduction") is not False:
        issues.append("staging_environment_source_not_isolated")
    if str(flags.get("RAZORPAY_MODE", "")).casefold() != "test":
        issues.append("razorpay_not_test_mode")
    for key in REQUIRED_DISABLED:
        if str(flags.get(key, "")).casefold() not in DISABLED:
            issues.append("external_side_effects_enabled_or_unknown:" + key)
    if origin.get("is_localhost") is not True or origin.get("is_public_site") is not False:
        issues.append("staging_public_origin_not_local")
    if frontend_auth.get("active_bundle_comparison_performed") is not True:
        issues.append("frontend_firebase_active_config_comparison_missing")
    if frontend_auth.get("stage_project_distinct_from_production") is not True:
        issues.append("firebase_project_not_isolated")
    if frontend_auth.get("stage_auth_domain_distinct_from_production") is not True:
        issues.append("firebase_auth_domain_not_isolated")
    if not isinstance(env_keys, list) or any(not isinstance(k, str) for k in env_keys):
        issues.append("staging_environment_key_inventory_missing")
    else:
        present = {key.upper() for key in env_keys}
        if present.intersection(PROHIBITED_STAGING_KEY_NAMES):
            issues.append("payment_or_messaging_credentials_in_staging_env")
    for port in PROD_PORTS:
        info = listeners.get(port)
        if not isinstance(info, dict) or info.get("loopback_only") is not True:
            issues.append("production_listener_exposure_unknown:" + port)
    network_policy = (
        stage.get("PrivateNetwork") == "yes"
        or bool(stage.get("NetworkNamespacePath"))
        or stage.get("IPAddressDeny") in ("any", "0.0.0.0/0 ::/0")
    )
    if not network_policy:
        issues.append("staging_shared_host_network_without_service_policy")
    # These MUST come from real, non-destructive testing conducted under the
    # staging process identity and namespace, not simply from unit properties.
    if evidence.get("production_loopback_api_blocked") is not True:
        issues.append("production_localhost_api_denial_not_verified")
    if evidence.get("external_egress_policy_verified") is not True:
        issues.append("external_egress_restrictions_not_verified")
    if evidence.get("authentication_credentials_distinct") is not True:
        issues.append("authentication_credential_separation_not_verified")
    if evidence.get("staging_health_after_network_policy") is not True:
        issues.append("staging_health_after_network_policy_not_verified")

    return {
        "passed": not issues,
        "issues": sorted(set(issues)),
        "static_side_effect_modes_safe": all(
            str(flags.get(k, "")).casefold() in DISABLED for k in REQUIRED_DISABLED
        ) and str(flags.get("RAZORPAY_MODE", "")).casefold() == "test",
        "network_policy_configured": network_policy,
        "firebase_frontend_isolated": all(
            frontend_auth.get(key) is True for key in (
                "active_bundle_comparison_performed",
                "stage_project_distinct_from_production",
                "stage_auth_domain_distinct_from_production",
            )
        ),
        "runtime_evidence_present": all(evidence.get(key) is True for key in (
            "production_loopback_api_blocked",
            "external_egress_policy_verified",
            "authentication_credentials_distinct",
            "staging_health_after_network_policy",
        )),
        "warning": "This offline preflight cannot itself certify the provenance of runtime evidence or complete security isolation.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline staging network/external credential release preflight")
    ap.add_argument("--snapshot", required=True, type=Path)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    result = check(json.loads(args.snapshot.read_text(encoding="utf-8")))
    output = json.dumps(result, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
