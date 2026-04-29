"""Delete-confirmation modal for sticky-note annotations.

Mounted at layout level (always available). The 🗑 button on each sticky
opens this modal via `manage_delete_modal` in callbacks/annotation_manager.py
— deletion only happens after the user clicks Delete here.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dcc


def render() -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Delete annotation?"), close_button=True),
            dbc.ModalBody(
                "This will permanently remove the annotation and its tags. "
                "Are you sure?"
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Cancel",
                        id="ann-delete-cancel-btn",
                        color="secondary",
                        outline=True,
                    ),
                    dbc.Button(
                        "Delete",
                        id="ann-delete-confirm-btn",
                        color="danger",
                    ),
                ]
            ),
            # Holds the annotation id awaiting confirmation. Cleared after
            # a confirm or cancel; overwritten on each 🗑 click.
            dcc.Store(id="ann-pending-delete-id", data=None),
        ],
        id="ann-delete-confirm-modal",
        is_open=False,
        size="sm",
        backdrop="static",
        centered=True,
    )
