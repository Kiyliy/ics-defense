"""
processor 模块 — 事件处理管线

将多源原始事件经过 规范化 → 聚簇 → 分级 → 入库/投递 的完整流程。
"""

from .pipeline import Pipeline

__all__ = ["Pipeline"]
