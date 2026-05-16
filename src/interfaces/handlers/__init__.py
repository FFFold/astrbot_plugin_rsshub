"""命令处理器模块（纯函数）"""

from .subscription import (
    handle_sub,
    handle_unsub,
    handle_sub_list,
    handle_refresh,
    handle_sub_state,
)
from .config import (
    handle_sub_set,
    handle_sub_set_user,
    handle_sub_get_user,
    handle_sub_set_session,
    handle_sub_get_session,
)
from .batch import (
    handle_batch_activate,
    handle_batch_deactivate,
    handle_unsub_all,
    handle_batch_unsub,
)
from .data import (
    handle_export,
    handle_import,
)
from .admin import (
    handle_test_sub,
    handle_admin_panel,
)

__all__ = [
    "handle_sub",
    "handle_unsub",
    "handle_sub_list",
    "handle_refresh",
    "handle_sub_state",
    "handle_sub_set",
    "handle_sub_set_user",
    "handle_sub_get_user",
    "handle_sub_set_session",
    "handle_sub_get_session",
    "handle_batch_activate",
    "handle_batch_deactivate",
    "handle_unsub_all",
    "handle_batch_unsub",
    "handle_export",
    "handle_import",
    "handle_test_sub",
    "handle_admin_panel",
]