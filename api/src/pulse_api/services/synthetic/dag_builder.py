"""Static pipeline topology definitions for synthetic data generation.

Three named pipelines of increasing complexity:
  jaffle-shop-analytics  — 12 nodes, dbt-style analytics (1 run/day)
  payments-pipeline      — 28 nodes, payment processing  (4 runs/day)
  ml-feature-store       — 45 nodes, ML feature compute  (2 runs/day)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeDefinition:
    external_id: str
    name: str
    node_type: str  # 'source' | 'model' | 'seed' | 'test'
    base_row_count: int
    base_duration_ms: int
    failure_rate: float = 0.03  # base per-run probability of failure
    is_flaky: bool = False  # if True, failure_rate is tripled


@dataclass
class AnomalyInjection:
    """A pre-baked anomaly injected into the simulated metric time-series."""

    node_external_id: str
    metric_name: str  # 'row_count' | 'duration_ms'
    day_start: int  # 0-indexed from sim_start (inclusive)
    day_end: int  # 0-indexed from sim_start (inclusive)
    value_multiplier: float  # applied to the node's base value
    severity: str  # 'low' | 'medium' | 'high' | 'critical'
    description: str


@dataclass
class PipelineDefinition:
    slug: str
    name: str
    description: str
    runs_per_day: int
    run_hours: list[int]  # UTC hours when runs start
    nodes: list[NodeDefinition]
    edges: list[tuple[str, str]]  # (source_external_id, target_external_id)
    source_type: str = "synthetic"
    # Days in the 90-day window with elevated failure rates (0-indexed, inclusive)
    bad_period: tuple[int, int] | None = None
    # Per-node failure rate multiplier during bad period. Unlisted nodes get bad_period_default.
    bad_period_node_multipliers: dict[str, float] = field(default_factory=dict)
    bad_period_default_multiplier: float = 5.0
    anomaly_injections: list[AnomalyInjection] = field(default_factory=list)


# ── Pipeline 1: jaffle-shop-analytics ─────────────────────────────────────────
_JAFFLE_NODES: list[NodeDefinition] = [
    # Sources
    NodeDefinition("raw_orders", "Raw Orders", "source", 50_000, 300),
    NodeDefinition("raw_customers", "Raw Customers", "source", 12_000, 200),
    NodeDefinition("raw_payments", "Raw Payments", "source", 48_000, 280),
    # Staging
    NodeDefinition("stg_orders", "Staged Orders", "model", 49_500, 900),
    NodeDefinition("stg_customers", "Staged Customers", "model", 11_800, 700),
    NodeDefinition("stg_payments", "Staged Payments", "model", 47_600, 850),
    # Core
    NodeDefinition("orders", "Orders", "model", 47_000, 1_500),
    NodeDefinition("customers", "Customers", "model", 11_500, 1_200),
    NodeDefinition("payments", "Payments", "model", 46_000, 1_400),
    # Marts
    NodeDefinition("revenue_summary", "Revenue Summary", "model", 365, 2_200),
    NodeDefinition("customer_ltv", "Customer LTV", "model", 11_000, 2_500),
    NodeDefinition("final_dashboard", "Final Dashboard", "model", 12, 800),
]

_JAFFLE_EDGES: list[tuple[str, str]] = [
    ("raw_orders", "stg_orders"),
    ("raw_customers", "stg_customers"),
    ("raw_payments", "stg_payments"),
    ("stg_orders", "orders"),
    ("stg_customers", "customers"),
    ("stg_payments", "payments"),
    ("orders", "revenue_summary"),
    ("payments", "revenue_summary"),
    ("customers", "customer_ltv"),
    ("orders", "customer_ltv"),
    ("revenue_summary", "final_dashboard"),
    ("customer_ltv", "final_dashboard"),
]

JAFFLE_SHOP = PipelineDefinition(
    slug="jaffle-shop-analytics",
    name="Jaffle Shop Analytics",
    description="dbt analytics pipeline for the Jaffle Shop demo project. "
    "Transforms raw orders, customers, and payments into revenue and LTV marts.",
    runs_per_day=1,
    run_hours=[1],
    nodes=_JAFFLE_NODES,
    edges=_JAFFLE_EDGES,
    bad_period=(25, 27),
    bad_period_default_multiplier=5.0,
    anomaly_injections=[
        AnomalyInjection(
            node_external_id="revenue_summary",
            metric_name="row_count",
            day_start=30,
            day_end=30,
            value_multiplier=0.12,
            severity="critical",
            description=(
                "Row count dropped 88% vs. 14-day average "
                "(365 → ~44 rows). Possible upstream filter bug."
            ),
        )
    ],
)


# ── Pipeline 2: payments-pipeline ─────────────────────────────────────────────
_PAYMENTS_NODES: list[NodeDefinition] = [
    # Sources
    NodeDefinition("txn_events", "Transaction Events", "source", 250_000, 500),
    NodeDefinition("account_data", "Account Data", "source", 85_000, 300),
    NodeDefinition("merchant_data", "Merchant Data", "source", 15_000, 200),
    NodeDefinition("risk_signals", "Risk Signals", "source", 120_000, 400),
    # Staging
    NodeDefinition("stg_txn_events", "Staged Transactions", "model", 248_000, 2_500, is_flaky=True),
    NodeDefinition("stg_account_data", "Staged Accounts", "model", 84_500, 1_800),
    NodeDefinition("stg_merchant_data", "Staged Merchants", "model", 14_800, 1_200),
    NodeDefinition("stg_risk_signals", "Staged Risk Signals", "model", 119_000, 2_000),
    # Intermediate
    NodeDefinition("int_txn_enriched", "Enriched Transactions", "model", 247_000, 3_500),
    NodeDefinition("int_txn_categorized", "Categorized Transactions", "model", 247_000, 2_800),
    NodeDefinition("int_account_balances", "Account Balances", "model", 84_000, 2_200),
    NodeDefinition("int_merchant_metrics", "Merchant Metrics", "model", 14_500, 1_500),
    NodeDefinition("int_risk_scores", "Risk Scores", "model", 120_000, 3_000),
    NodeDefinition("int_daily_volumes", "Daily Volumes", "model", 2_000, 1_800),
    NodeDefinition("int_payment_methods", "Payment Methods", "model", 8, 500),
    NodeDefinition("int_hourly_agg", "Hourly Aggregation", "model", 24, 600),
    # Core
    NodeDefinition("transactions", "Transactions", "model", 245_000, 5_000),
    NodeDefinition("accounts", "Accounts", "model", 83_000, 3_500),
    NodeDefinition("merchants", "Merchants", "model", 14_000, 2_000),
    NodeDefinition("payments_ledger", "Payments Ledger", "model", 240_000, 6_000),
    NodeDefinition("risk_assessments", "Risk Assessments", "model", 118_000, 4_500),
    NodeDefinition("volume_metrics", "Volume Metrics", "model", 96, 800),
    # Marts
    NodeDefinition("revenue_report", "Revenue Report", "model", 500, 2_500),
    NodeDefinition("fraud_report", "Fraud Report", "model", 1_200, 3_000),
    NodeDefinition("merchant_report", "Merchant Report", "model", 300, 1_800),
    NodeDefinition("account_report", "Account Report", "model", 2_000, 2_200),
    NodeDefinition("ops_dashboard", "Ops Dashboard", "model", 48, 1_200),
    NodeDefinition("compliance_export", "Compliance Export", "model", 800, 2_000),
]

_PAYMENTS_EDGES: list[tuple[str, str]] = [
    # Sources → Staging
    ("txn_events", "stg_txn_events"),
    ("account_data", "stg_account_data"),
    ("merchant_data", "stg_merchant_data"),
    ("risk_signals", "stg_risk_signals"),
    # Staging → Intermediate
    ("stg_txn_events", "int_txn_enriched"),
    ("stg_account_data", "int_txn_enriched"),
    ("stg_txn_events", "int_txn_categorized"),
    ("stg_merchant_data", "int_txn_categorized"),
    ("stg_account_data", "int_account_balances"),
    ("stg_merchant_data", "int_merchant_metrics"),
    ("stg_risk_signals", "int_risk_scores"),
    ("stg_txn_events", "int_risk_scores"),
    ("int_txn_enriched", "int_daily_volumes"),
    ("stg_txn_events", "int_payment_methods"),
    ("int_txn_enriched", "int_hourly_agg"),
    # Intermediate → Core
    ("int_txn_enriched", "transactions"),
    ("int_txn_categorized", "transactions"),
    ("int_risk_scores", "transactions"),
    ("int_account_balances", "accounts"),
    ("int_merchant_metrics", "merchants"),
    ("transactions", "payments_ledger"),
    ("int_risk_scores", "risk_assessments"),
    ("transactions", "risk_assessments"),
    ("int_daily_volumes", "volume_metrics"),
    ("int_hourly_agg", "volume_metrics"),
    # Core → Marts
    ("payments_ledger", "revenue_report"),
    ("volume_metrics", "revenue_report"),
    ("risk_assessments", "fraud_report"),
    ("merchants", "merchant_report"),
    ("transactions", "merchant_report"),
    ("accounts", "account_report"),
    ("payments_ledger", "account_report"),
    ("volume_metrics", "ops_dashboard"),
    ("risk_assessments", "ops_dashboard"),
    ("payments_ledger", "compliance_export"),
    ("risk_assessments", "compliance_export"),
    ("accounts", "compliance_export"),
]

PAYMENTS_PIPELINE = PipelineDefinition(
    slug="payments-pipeline",
    name="Payments Pipeline",
    description="Real-time payment processing pipeline. Ingests transaction events, "
    "account data, merchant info, and risk signals. Produces reconciliation, "
    "fraud analysis, and compliance exports.",
    runs_per_day=4,
    run_hours=[0, 6, 12, 18],
    nodes=_PAYMENTS_NODES,
    edges=_PAYMENTS_EDGES,
    bad_period=(42, 44),
    bad_period_default_multiplier=4.0,
    anomaly_injections=[
        AnomalyInjection(
            node_external_id="stg_txn_events",
            metric_name="duration_ms",
            day_start=45,
            day_end=47,
            value_multiplier=5.2,
            severity="high",
            description=(
                "Processing time increased 420% vs. 14-day average "
                "(2.5s → ~13s). Possible index degradation or resource contention."
            ),
        )
    ],
)


# ── Pipeline 3: ml-feature-store ──────────────────────────────────────────────
_ML_NODES: list[NodeDefinition] = [
    # Raw (5)
    NodeDefinition("user_events", "User Events", "source", 2_000_000, 800),
    NodeDefinition("product_catalog", "Product Catalog", "source", 50_000, 300),
    NodeDefinition("session_logs", "Session Logs", "source", 5_000_000, 1_200),
    NodeDefinition("purchase_history", "Purchase History", "source", 800_000, 600),
    NodeDefinition("ab_experiments", "A/B Experiments", "source", 100_000, 400),
    # Base features (5)
    NodeDefinition("user_base_features", "User Base Features", "model", 500_000, 5_000),
    NodeDefinition("product_base_features", "Product Base Features", "model", 45_000, 2_000),
    NodeDefinition("session_base_features", "Session Base Features", "model", 4_000_000, 8_000),
    NodeDefinition("purchase_base_features", "Purchase Base Features", "model", 750_000, 4_500),
    NodeDefinition("experiment_assignments", "Experiment Assignments", "model", 95_000, 2_000),
    # Derived user features (5)
    NodeDefinition("user_engagement_features", "User Engagement", "model", 490_000, 3_000),
    NodeDefinition("user_retention_features", "User Retention", "model", 490_000, 2_800),
    NodeDefinition("user_purchase_features", "User Purchase", "model", 480_000, 3_200),
    NodeDefinition("user_session_features", "User Session", "model", 490_000, 2_500),
    NodeDefinition("user_ab_features", "User A/B Features", "model", 95_000, 1_500),
    # Derived product features (5)
    NodeDefinition("product_popularity", "Product Popularity", "model", 44_000, 1_800),
    NodeDefinition("product_conversion", "Product Conversion", "model", 44_000, 1_600),
    NodeDefinition("product_recommendations", "Product Recommendations", "model", 43_000, 2_200),
    NodeDefinition("product_inventory", "Product Inventory", "model", 44_000, 1_200),
    NodeDefinition("product_pricing", "Product Pricing", "model", 43_000, 1_400),
    # Cross features (5)
    NodeDefinition("user_product_affinity", "User-Product Affinity", "model", 2_000_000, 6_000),
    NodeDefinition("session_conversion", "Session Conversion", "model", 1_000_000, 4_500),
    NodeDefinition("purchase_propensity", "Purchase Propensity", "model", 480_000, 5_000),
    NodeDefinition("churn_risk_score", "Churn Risk Score", "model", 490_000, 4_000),
    NodeDefinition("growth_potential", "Growth Potential", "model", 490_000, 3_500),
    # Aggregations (10)
    NodeDefinition("user_daily_agg", "User Daily Aggregation", "model", 500_000, 3_000),
    NodeDefinition("user_weekly_agg", "User Weekly Aggregation", "model", 450_000, 2_500),
    NodeDefinition("user_monthly_agg", "User Monthly Aggregation", "model", 400_000, 2_000),
    NodeDefinition("product_daily_agg", "Product Daily Aggregation", "model", 45_000, 1_500),
    NodeDefinition("product_weekly_agg", "Product Weekly Aggregation", "model", 44_000, 1_200),
    NodeDefinition("session_quality_agg", "Session Quality Aggregation", "model", 100_000, 2_000),
    NodeDefinition("purchase_frequency_agg", "Purchase Frequency", "model", 480_000, 1_800),
    NodeDefinition("content_affinity_agg", "Content Affinity Aggregation", "model", 2_000_000, 4_000),
    NodeDefinition("platform_health_agg", "Platform Health Aggregation", "model", 1_000, 500),
    NodeDefinition("experiment_metrics_agg", "Experiment Metrics", "model", 95_000, 1_500),
    # Outputs (10)
    NodeDefinition("training_features", "Training Features", "model", 3_000_000, 8_000),
    NodeDefinition("serving_features_v1", "Serving Features v1", "model", 500_000, 4_000),
    NodeDefinition("serving_features_v2", "Serving Features v2", "model", 500_000, 5_000),
    NodeDefinition("monitoring_features", "Monitoring Features", "model", 500_000, 2_000),
    NodeDefinition("backfill_features", "Backfill Features", "model", 10_000_000, 25_000),
    NodeDefinition("validation_report", "Validation Report", "model", 200, 3_000),
    NodeDefinition("feature_drift_report", "Feature Drift Report", "model", 500_000, 4_000),
    NodeDefinition("data_quality_report", "Data Quality Report", "model", 100, 1_000),
    NodeDefinition("feature_catalog_update", "Feature Catalog Update", "model", 1_000, 500),
    NodeDefinition("downstream_ml_trigger", "Downstream ML Trigger", "model", 1, 200),
]

_ML_EDGES: list[tuple[str, str]] = [
    # Raw → Base
    ("user_events", "user_base_features"),
    ("product_catalog", "product_base_features"),
    ("session_logs", "session_base_features"),
    ("purchase_history", "purchase_base_features"),
    ("ab_experiments", "experiment_assignments"),
    # Base → Derived user features
    ("user_base_features", "user_engagement_features"),
    ("session_base_features", "user_engagement_features"),
    ("user_base_features", "user_retention_features"),
    ("purchase_base_features", "user_retention_features"),
    ("user_base_features", "user_purchase_features"),
    ("purchase_base_features", "user_purchase_features"),
    ("user_base_features", "user_session_features"),
    ("session_base_features", "user_session_features"),
    ("user_base_features", "user_ab_features"),
    ("experiment_assignments", "user_ab_features"),
    # Base → Derived product features
    ("product_base_features", "product_popularity"),
    ("purchase_base_features", "product_popularity"),
    ("product_base_features", "product_conversion"),
    ("session_base_features", "product_conversion"),
    ("product_base_features", "product_recommendations"),
    ("user_engagement_features", "product_recommendations"),
    ("product_base_features", "product_inventory"),
    ("product_base_features", "product_pricing"),
    ("purchase_base_features", "product_pricing"),
    # Derived → Cross features
    ("user_engagement_features", "user_product_affinity"),
    ("product_recommendations", "user_product_affinity"),
    ("user_session_features", "session_conversion"),
    ("product_conversion", "session_conversion"),
    ("user_purchase_features", "purchase_propensity"),
    ("product_popularity", "purchase_propensity"),
    ("user_retention_features", "churn_risk_score"),
    ("user_ab_features", "churn_risk_score"),
    ("user_retention_features", "growth_potential"),
    ("user_purchase_features", "growth_potential"),
    # → Aggregations
    ("user_engagement_features", "user_daily_agg"),
    ("user_session_features", "user_daily_agg"),
    ("user_daily_agg", "user_weekly_agg"),
    ("user_weekly_agg", "user_monthly_agg"),
    ("product_popularity", "product_daily_agg"),
    ("product_conversion", "product_daily_agg"),
    ("product_daily_agg", "product_weekly_agg"),
    ("session_conversion", "session_quality_agg"),
    ("purchase_propensity", "purchase_frequency_agg"),
    ("user_product_affinity", "content_affinity_agg"),
    ("user_daily_agg", "platform_health_agg"),
    ("product_daily_agg", "platform_health_agg"),
    ("session_quality_agg", "platform_health_agg"),
    ("churn_risk_score", "experiment_metrics_agg"),
    ("growth_potential", "experiment_metrics_agg"),
    ("user_ab_features", "experiment_metrics_agg"),
    # → Outputs
    ("user_monthly_agg", "training_features"),
    ("product_weekly_agg", "training_features"),
    ("content_affinity_agg", "training_features"),
    ("purchase_frequency_agg", "training_features"),
    ("user_daily_agg", "serving_features_v1"),
    ("product_daily_agg", "serving_features_v1"),
    ("churn_risk_score", "serving_features_v1"),
    ("user_daily_agg", "serving_features_v2"),
    ("product_daily_agg", "serving_features_v2"),
    ("churn_risk_score", "serving_features_v2"),
    ("growth_potential", "serving_features_v2"),
    ("serving_features_v1", "monitoring_features"),
    ("platform_health_agg", "monitoring_features"),
    ("training_features", "backfill_features"),
    ("serving_features_v1", "validation_report"),
    ("serving_features_v2", "validation_report"),
    ("user_monthly_agg", "feature_drift_report"),
    ("serving_features_v1", "feature_drift_report"),
    ("monitoring_features", "data_quality_report"),
    ("validation_report", "feature_catalog_update"),
    ("data_quality_report", "feature_catalog_update"),
    ("feature_catalog_update", "downstream_ml_trigger"),
]

ML_FEATURE_STORE = PipelineDefinition(
    slug="ml-feature-store",
    name="ML Feature Store",
    description="Feature computation pipeline for machine learning models. "
    "Computes user, product, and cross features; produces training and serving datasets. "
    "45 nodes with fan-out topology.",
    runs_per_day=2,
    run_hours=[2, 14],
    nodes=_ML_NODES,
    edges=_ML_EDGES,
    bad_period=(58, 60),
    bad_period_node_multipliers={"user_events": 30.0},
    bad_period_default_multiplier=1.0,  # Only user_events fails; cascade handles the rest
    anomaly_injections=[
        AnomalyInjection(
            node_external_id="user_daily_agg",
            metric_name="row_count",
            day_start=58,
            day_end=60,
            value_multiplier=0.0,
            severity="critical",
            description=(
                "Row count dropped to 0 for 3 consecutive days "
                "due to upstream user_events source failure."
            ),
        )
    ],
)


PIPELINE_DEFINITIONS: list[PipelineDefinition] = [
    JAFFLE_SHOP,
    PAYMENTS_PIPELINE,
    ML_FEATURE_STORE,
]
