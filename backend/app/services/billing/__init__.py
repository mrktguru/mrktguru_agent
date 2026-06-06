"""Credit billing: token metering, budget guard, settlement, analytics.

See CREDIT_MECHANICS.md. A credit is a fixed abstraction over USD
(1 credit = $0.01); models/prices change here without touching the UI.
"""
