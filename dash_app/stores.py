"""IDs for `dcc.Store` components — referenced by both layout and callbacks.

Centralized so a typo'd ID becomes an attribute error instead of a silent
no-op (Dash doesn't validate Store IDs at startup).
"""

DATA_VERSION = "data-version"
ANNOTATIONS_VERSION = "annotations-version"
SELECTED_RANGE = "selected-range"
ACTIVE_ACCOUNT_ID = "active-account-id"
SYNC_PROGRESS = "sync-progress"
