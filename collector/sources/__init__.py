"""数据源采集器模块

提供面向不同安全设备的采集器实现：
- WAFCollector: 雷池 WAF
- NIDSCollector: Suricata NIDS
- HIDSCollector: Wazuh HIDS
- SOCCollector: 通用 SOC/Syslog
- PikachuCollector: PIKACHU 靶场
"""

from .base import BaseCollector
from .waf_collector import WAFCollector
from .nids_collector import NIDSCollector
from .hids_collector import HIDSCollector
from .soc_collector import SOCCollector
from .pikachu_collector import PikachuCollector

__all__ = [
    "BaseCollector",
    "WAFCollector",
    "NIDSCollector",
    "HIDSCollector",
    "SOCCollector",
    "PikachuCollector",
]
