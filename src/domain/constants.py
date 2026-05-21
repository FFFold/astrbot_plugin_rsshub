"""
领域层共享常量

存放领域层各模块共用的常量值，避免重复定义。
"""

# 配置继承标记值：表示该配置项应继承自上层（订阅→用户→全局）
INHERIT_VALUE = -100

# 用户状态
USER_STATE_BANNED = -1
USER_STATE_USER = 1

# Feed / 订阅状态
STATE_DISABLED = 0
STATE_ENABLED = 1

# 通知设置
NOTIFY_DISABLED = 0
NOTIFY_ENABLED = 1

# 发送模式
SEND_MODE_LINK_ONLY = -1
SEND_MODE_AUTO = 0
SEND_MODE_DIRECT = 1
