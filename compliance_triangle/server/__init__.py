"""Multi-tenant SaaS layer for compliance-triangle (stdlib only).

This package adds accounts, persistence, quotas and a JSON API *on top of* the
existing verification engine. The engine itself
(``compliance_triangle.verify_integration``, ``citation_parser``, ``kb``) is
deliberately left untouched — it is already covered by the test-suite, and
rewriting verified logic would be a regression risk with no payoff.

Submodules:
    store  — SQLite persistence (users / sessions / api_keys / analyses / usage)
    auth   — password hashing, session + API-key primitives
    app    — HTTP routing, authentication, quota enforcement, static assets
"""
